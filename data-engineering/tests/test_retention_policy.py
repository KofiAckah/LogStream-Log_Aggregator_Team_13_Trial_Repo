"""Tests for scripts/retention_policy.py — Retention enforcement logic."""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta


class TestGetRetentionPolicies:
    """Tests for fetching retention policies from the database."""

    @patch("retention_policy.pd.read_sql")
    @patch("retention_policy.engine")
    def test_returns_policies(self, mock_engine, mock_read_sql, sample_retention_policies_df):
        """Should return a DataFrame of active retention policies."""
        from retention_policy import get_retention_policies
        mock_read_sql.return_value = sample_retention_policies_df

        result = get_retention_policies()
        assert not result.empty
        assert "log_level" in result.columns
        assert "retention_days" in result.columns


class TestEnforceRetention:
    """Tests for the retention enforcement logic."""

    @patch("retention_policy.pd.DataFrame.to_csv")
    @patch("retention_policy.pd.read_sql")
    @patch("retention_policy.engine")
    @patch("retention_policy.get_retention_policies")
    def test_detaches_and_drops_partition(self, mock_get_policies, mock_engine, mock_read_sql_partition, mock_to_csv):
        """Should detach and drop partitions that match expired policies, archiving them first."""
        from retention_policy import enforce_retention

        mock_get_policies.return_value = pd.DataFrame({
            "log_level": ["INFO"],
            "retention_days": [30],
        })

        # Mock the connection context manager
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)
        # Simulate that the partition exists
        mock_conn.execute.return_value.scalar.return_value = 1
        
        # Simulate that the partition has data to archive
        mock_read_sql_partition.return_value = pd.DataFrame({"id": [1, 2]})

        enforce_retention()

        # Should have called to_csv to save the archive
        mock_to_csv.assert_called_once()
        # Should have called execute at least 3 times:
        # 1. Check partition exists, 2. DETACH, 3. DROP
        assert mock_conn.execute.call_count >= 3

    @patch("retention_policy.engine")
    @patch("retention_policy.get_retention_policies")
    def test_falls_back_to_default_30_days(self, mock_get_policies, mock_engine):
        """When no policies exist, should fall back to 30-day default."""
        from retention_policy import enforce_retention

        mock_get_policies.return_value = pd.DataFrame()

        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.scalar.return_value = 0

        enforce_retention()
        # Should still run (with the default policy) and not crash
        mock_conn.execute.assert_called()

    @patch("retention_policy.engine")
    @patch("retention_policy.get_retention_policies")
    def test_skips_nonexistent_partition(self, mock_get_policies, mock_engine):
        """Should skip partitions that don't exist in the database."""
        from retention_policy import enforce_retention

        mock_get_policies.return_value = pd.DataFrame({
            "log_level": ["ERROR"],
            "retention_days": [90],
        })

        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)
        # Simulate partition does NOT exist
        mock_conn.execute.return_value.scalar.return_value = 0

        enforce_retention()
        # Only 1 call (the existence check) — no DETACH or DROP
        assert mock_conn.execute.call_count == 1

    @patch("retention_policy.engine")
    @patch("retention_policy.get_retention_policies")
    def test_handles_error_per_partition(self, mock_get_policies, mock_engine):
        """Errors on one partition should not crash the entire enforcement run."""
        from retention_policy import enforce_retention

        mock_get_policies.return_value = pd.DataFrame({
            "log_level": ["INFO"],
            "retention_days": [30],
        })

        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)
        # Simulate partition exists but DETACH fails
        mock_conn.execute.return_value.scalar.return_value = 1
        mock_conn.execute.side_effect = [
            MagicMock(scalar=MagicMock(return_value=1)),  # exists check
            Exception("Permission denied"),  # DETACH fails
        ]

        # Should NOT raise
        enforce_retention()
