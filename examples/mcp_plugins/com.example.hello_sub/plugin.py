"""示例外挂：python-subprocess runtime."""


def register(host):
    @host.tool(
        name="example.hello_sub",
        description="子进程插件打招呼。参数 name 可选。",
        props=[{"name": "name", "type": "string", "default": "世界"}],
    )
    async def hello(args):
        name = (args or {}).get("name") or "世界"
        return f"你好, {name}！（subprocess 插件 com.example.hello_sub）"
