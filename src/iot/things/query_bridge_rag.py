from src.iot.thing import Thing, Parameter, ValueType


def get_rag_result(qurey):
    """
    介绍莱斯城市治理系统

    返回:
        str: 介绍信息
    """
    print("查询：",qurey)
    introduction = "这里是你查询的函数，并且返回内容得地方"
    return introduction


class QueryBridgeRAG(Thing):
    def __init__(self):
        super().__init__("查询桥接器", "联网查询信息并存储结果")
        # 存储查询到的内容
        self.query_result = ""
        self.last_query = ""
        
        # 注册属性
        self.add_property("query_result", "当前查询结果", lambda: self.query_result)
        self.add_property("last_query", "上次查询内容", lambda: self.last_query)
        
        self._register_methods()

    def _register_methods(self):
        # 查询信息
        self.add_method(
            "Query",
            "查询信息",
            [Parameter("query", "查询内容", ValueType.STRING, True)],
            lambda params: self._query_info_and_store(params["query"].get_value())
        )
        
        # 获取查询结果
        self.add_method(
            "GetQueryResult",
            "获取查询结果",
            [],
            lambda params: {"result": self.query_result, "query": self.last_query}
        )
    
    def _query_info(self, query):
        """
        查询信息
        
        参数:
            query (str): 查询内容
            
        返回:
            str: 查询结果
        """
        try:
            # 调用逻辑层的 RAG 知识库查询
            result = get_rag_result(query)
            # rag 查询

            # 其他的联网方式例如dify


            return result
        except Exception as e:
            print(f"查询信息失败: {e}")
            return f"很抱歉，查询'{query}'时出现了错误。"
    
    def _query_info_and_store(self, query):
        """
        查询信息并存储
        
        参数:
            query (str): 查询内容
            
        返回:
            dict: 操作结果
        """
        try:
            # 记录查询内容
            self.last_query = query
            
            # 查询信息并存储
            self.query_result = self._query_info(query)
            
            return {
                "success": True, 
                "message": "查询成功", 
                "result": self.query_result
            }
        except Exception as e:
            return {"success": False, "message": f"查询失败: {e}"}

