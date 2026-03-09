"""Tests for scripts/retention_policy.py — Per-service retention enforcement logic."""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta


class TestGetRetentionPolicies:
    """Tests for fetching retention policies from the database."""

    @patch("retention_policy.pd.read_sql")
    @patch("retention_policy.engine")
    def test_returns_policies(self, mock_engine, mock_read_sql):
        """Should return a DataFrame of active retention policies including service_name."""
        from retention_policy import get_retention_policies

        expected = pd.DataFrame({
            "service_name": ["auth-service", None],
            "log_level": ["ERROR", "INFO"],
            "retention_days": [90, 30],
        })
        mock_read_sql.return_value = expected

        result = get_retention_policies()
        assert not result.empty
        assert "service_name" in result.columns
        assert "log_level" in result.columns
        assert "retention_days" in result.columns


class TestEnforceRetention:
    """Tests for the per-service retention enforcement logic."""

    @patch("retention_policy.Path")
    @patch("retention_policy.pd.DataFrame.to_csv")
    @patch("retention_policy.pd.read_sql")
    @patch("retention_policy.engine")
    @patch("retention_policy.get_retention_policies")
    def test_archives_and_deletes_per_service(self, mock_get_policies, mock_engine,
                                               mock_read_sql, mock_to_csv, mock_path):
        """Should select expired rows for a specific service, archive to CSV, and delete."""
        from retention_policy import enforce_retention

        mock_get_policies.return_value = pd.DataFrame({
            "service_name": ["auth-service"],
            "log_level": ["ERROR"],
            "retention_days": [30],
        })

        # Mock connection
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        # Mock read_sql to return expired rows
        mock_read_sql.return_value = pd.DataFrame({
            "id": ["uuid-1", "uuid-2"],
            "timestamp": [datetime(2024, 1, 1), datetime(2024, 1, 2)],
            "level": ["ERROR", "ERROR"],
            "service_name": ["auth-service", "auth-service"],
        })

        # Mock delete result
        mock_conn.execute.return_value.rowcount = 2

        # Mock Path for archive directory
        mock_archive_dir = MagicMock()
        mock_path.return_value.__truediv__ = MagicMock(return_value=mock_archive_dir)

        enforce_retention()

        # Should have archived to CSV
        mock_to_csv.assert_called_once()
        # Should have executed the DELETE query
        mock_conn.execute.assert_called()

    @patch("retention_policy.Path")
    @patch("retention_policy.pd.read_sql")
    @patch("retention_policy.engine")
    @patch("retention_policy.get_retention_policies")
    def test_falls_back_to_global_default(self, mock_get_policies, mock_engine,
                                           mock_read_sql, mock_path):
        """When no policies exist, should fall back to 30-day global default."""
        from retention_policy import enforce_retention

        mock_get_policies.return_value = pd.DataFrame()

        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        # No expired rows found
        mock_read_sql.return_value = pd.DataFrame()

        enforce_retention()
        # Should still run without crashing
        mock_read_sql.assert_called_once()

    @patch("retention_policy.Path")
    @patch("retention_policy.pd.read_sql")
    @patch("retention_policy.engine")
    @patch("retention_policy.get_retention_policies")
    def test_skips_when_no_expired_rows(self, mock_get_policies, mock_engine,
                                         mock_read_sql, mock_path):
        """Should skip CSV and DELETE when no expired rows are found."""
        from retention_policy import enforce_retention

        mock_get_policies.return_value = pd.DataFrame({
            "service_name": ["payment-api"],
            "log_level": ["INFO"],
            "retention_days": [90],
        })

        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        # No expired rows
        mock_read_sql.return_value = pd.DataFrame()

        enforce_retention()
        # Should NOT have called execute (no DELETE needed)
        mock_conn.execute.assert_not_called()

    @patch("retention_policy.Path")
    @patch("retention_policy.pd.read_sql")
    @patch("retention_policy.engine")
    @patch("retention_policy.get_retention_policies")
    def test_handles_error_per_policy(self, mock_get_policies, mock_engine,
                                       mock_read_sql, mock_path):
        """Errors on one policy should not crash the entire enforcement run."""
        from retention_policy import enforce_retention

        mock_get_policies.return_value = pd.DataFrame({
            "service_name": ["auth-service"],
            "log_level": ["ERROR"],
            "retention_days": [30],
        })

        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        # Simulate read_sql throwing an error
        mock_read_sql.side_effect = Exception("Connection lost")

        # Should NOT raise
        enforce_retention()

    @patch("retention_policy.Path")
    @patch("retention_policy.pd.DataFrame.to_csv")
    @patch("retention_policy.pd.read_sql")
    @patch("retention_policy.engine")
    @patch("retention_policy.get_retention_policies")
    def test_global_policy_applies_to_all(self, mock_get_policies, mock_engine,
                                           mock_read_sql, mock_to_csv, mock_path):
        """A policy with NULL service_name and NULL log_level should match all logs."""
        from retention_policy import enforce_retention

        mock_get_policies.return_value = pd.DataFrame({
            "service_name": [None],
            "log_level": [None],
            "retention_days": [7],
        })

        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        # Simulate expired rows
        mock_read_sql.return_value = pd.DataFrame({
            "id": ["uuid-1"],
            "timestamp": [datetime(2024, 1, 1)],
            "level": ["INFO"],
            "service_name": ["any-service"],
        })
        mock_conn.execute.return_value.rowcount = 1

        mock_archive_dir = MagicMock()
        mock_path.return_value.__truediv__ = MagicMock(return_value=mock_archive_dir)

        enforce_retention()

        # Should archive and delete
        mock_to_csv.assert_called_once()
        mock_conn.execute.assert_called()
