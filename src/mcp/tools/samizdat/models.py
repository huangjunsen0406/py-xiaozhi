import uuid
from datetime import datetime
from typing import Any, Dict

class SamizdatEntry:
    def __init__(
        self,
        Title: str,
        Text: str = "",
        AgentName: str ="",
        entry_Id: str = None,
    ):
        self.Id = entry_Id or str(uuid.uuid4())
        self.Title = Title
        self.Text = Text
        self.AgentName = AgentName
        self.CreatedTime = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典.
        """
        return {
            "Id": self.Id,
            "Title": self.Title,
            "CreatedTime": self.CreatedTime,
            "Text": self.Text,
            "AgentName": self.AgentName,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SamizdatEntry":
        """
        从字典创建事件.
        """
        entry = cls(
            Title=data["Title"],
            Text=data["Text"],
            entry_Id=data["Id"],
            AgentName=data["AgentName"],
        )
        entry.CreatedTime=data.get("CreatedTime", entry.CreatedTime)
        
        return entry

