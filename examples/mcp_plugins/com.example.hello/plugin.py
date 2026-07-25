"""示例外挂 MCP 插件：无第三方依赖，可直接拷贝到用户 mcp_plugins/."""


def register(host):
    @host.tool(
        name="example.hello",
        description="打招呼。参数 name 可选。用于验证外挂 MCP 插件是否加载成功。",
        props=[{"name": "name", "type": "string", "default": "世界"}],
    )
    async def hello(args):
        name = (args or {}).get("name") or "世界"
        return f"你好, {name}！（来自外挂插件 com.example.hello）"

    # 可选：只读配置
    cfg = host.get("config_readonly")
    log = host.get("logger")
    if log and cfg is not None:
        log.debug("[example.hello] 已拿到 config_readonly")
