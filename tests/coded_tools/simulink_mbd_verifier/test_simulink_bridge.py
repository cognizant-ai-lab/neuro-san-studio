from unittest import TestCase

from coded_tools.simulink_mbd_verifier.simulink_bridge import SimulinkMcpBridge


class TestSimulinkMcpBridge(TestCase):
    """Tests MATLAB error detection in Simulink MCP text responses."""

    def test_get_mcp_error_detects_matlab_status_text(self):
        """A MATLAB error embedded in ordinary MCP text must not be reported as success."""
        raw_output = (
            '\nans = \n\n    "status: error\n'
            '     error_code: MODEL_NOT_FOUND\n'
            '     message: "Model \'TempControlSystem\' not found""\n'
        )

        self.assertIn("MODEL_NOT_FOUND", SimulinkMcpBridge._get_mcp_error(raw_output))

    def test_get_mcp_error_detects_json_status(self):
        """A JSON-formatted error payload must also be recognized."""
        raw_output = '{"status": "error", "message": "Model not found"}'

        self.assertEqual(raw_output, SimulinkMcpBridge._get_mcp_error(raw_output))

    def test_get_mcp_error_returns_empty_for_success(self):
        """Successful MATLAB output must remain a success."""
        raw_output = '{"status": "success", "model": "ACC_Basic_Speed_Hold"}'

        self.assertEqual("", SimulinkMcpBridge._get_mcp_error(raw_output))

