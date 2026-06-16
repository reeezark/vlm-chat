"""工具调用测试。"""

from src import tools


def test_execute_tool_call_emits_audit_for_unknown_tool():
    events = []
    tools.set_tool_audit_hook(lambda name, success, detail: events.append((name, success, detail)))

    result = tools.execute_tool_call("unknown_tool", "{}")

    tools.set_tool_audit_hook(None)
    assert "未知工具" in result
    assert events == [("unknown_tool", False, result)]
