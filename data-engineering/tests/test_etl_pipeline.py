"""Tests for scripts/etl_pipeline.py — ETL transform and pipeline logic."""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock


class TestTransformHealthMetrics:
    """Unit tests for the transform_health_metrics function."""

    def test_normal_mixed_logs(self, sample_logs_df):
        """Should calculate correct error_rate and status for mixed log levels."""
        from etl_pipeline import transform_health_metrics
        result = transform_health_metrics(sample_logs_df)

        assert not result.empty
        assert "error_rate" in result.columns
        assert "status" in result.columns

        # auth-service: 1 ERROR out of 3 logs = 33.3% → CRITICAL
        auth = result[result["service_name"] == "auth-service"].iloc[0]
        assert auth["error_logs"] == 1
        assert auth["total_logs"] == 3
        assert auth["status"] == "CRITICAL"

    def test_empty_dataframe(self, empty_logs_df):
        """Should return empty DataFrame when input is empty."""
        from etl_pipeline import transform_health_metrics
        result = transform_health_metrics(empty_logs_df)
        assert result.empty

    def test_all_errors(self):
        """Status should be CRITICAL when all logs are errors."""
        from etl_pipeline import transform_health_metrics
        df = pd.DataFrame({
            "id": ["a", "b", "c"],
            "timestamp": pd.to_datetime(["2025-01-01"] * 3),
            "level": ["ERROR", "ERROR", "ERROR"],
            "message": ["fail"] * 3,
            "service_name": ["svc-a"] * 3,
            "source": ["app"] * 3,
        })
        result = transform_health_metrics(df)
        assert result.iloc[0]["error_rate"] == 100.0
        assert result.iloc[0]["status"] == "CRITICAL"

    def test_no_errors(self):
        """Status should be STABLE when there are zero errors."""
        from etl_pipeline import transform_health_metrics
        df = pd.DataFrame({
            "id": ["a", "b", "c"],
            "timestamp": pd.to_datetime(["2025-01-01"] * 3),
            "level": ["INFO", "WARN", "INFO"],
            "message": ["ok"] * 3,
            "service_name": ["svc-a"] * 3,
            "source": ["app"] * 3,
        })
        result = transform_health_metrics(df)
        assert result.iloc[0]["error_rate"] == 0.0
        assert result.iloc[0]["status"] == "STABLE"


class TestLoadData:
    """Tests for the load_data function."""

    def test_skips_empty_dataframe(self):
        """load_data should do nothing when given an empty DataFrame."""
        from etl_pipeline import load_data
        empty_df = pd.DataFrame()
        # Should not raise — just returns
        with patch("etl_pipeline.engine") as mock_engine:
            load_data(empty_df, "test_table")
            mock_engine.assert_not_called()


class TestRunPipeline:
    """Integration-level tests for the full pipeline run."""

    @patch("etl_pipeline.engine")
    @patch("etl_pipeline.load_data")
    @patch("etl_pipeline.extract_incremental_logs")
    @patch("etl_pipeline.manage_partitions")
    def test_pipeline_logs_success(self, mock_partitions, mock_extract, mock_load, mock_engine, sample_logs_df):
        """Pipeline should complete successfully with valid data."""
        from etl_pipeline import run_pipeline
        # Mock what extract_incremental_logs returns
        mock_extract.return_value = sample_logs_df

        # Mock connection for TRUNCATE and DELETE
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        run_pipeline()
        
        mock_partitions.assert_called_once()
        # It is called twice: once for 60 mins, once for 1440 mins
        assert mock_extract.call_count == 2
        # It is called twice: once for health dashboard, once for volume trends
        assert mock_load.call_count == 2

    @patch("etl_pipeline.load_data")
    @patch("etl_pipeline.extract_incremental_logs")
    @patch("etl_pipeline.manage_partitions")
    def test_pipeline_skips_on_empty(self, mock_partitions, mock_extract, mock_load, empty_logs_df):
        """Pipeline should skip transformation when no logs are found."""
        from etl_pipeline import run_pipeline
        mock_extract.return_value = empty_logs_df

        run_pipeline()
        
        # Called once for 60 mins, returns empty, so it safely exits
        mock_extract.assert_called_once()
        mock_load.assert_not_called()

    @patch("etl_pipeline.manage_partitions", side_effect=Exception("DB connection failed"))
    def test_pipeline_handles_exception(self, mock_partitions):
        """Pipeline should catch and log errors instead of crashing."""
        from etl_pipeline import run_pipeline
        # Should NOT raise — error is caught internally
        run_pipeline()
