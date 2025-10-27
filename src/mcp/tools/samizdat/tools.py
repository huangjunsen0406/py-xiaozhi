import json
from datetime import datetime, timedelta
from typing import Any, Dict

from src.utils.logging_config import get_logger

from .manager import get_samizdat_manager
from .models import SamizdatEntry

logger = get_logger(__name__)


async def add_entry(args: Dict[str, Any]) -> str:
    try:
        Title = args.get("Title","") 
        AgentName = args.get("AgentName","") 
        Text = args.get("Text","")

        # 创建事件
        entry = SamizdatEntry(
            Title=Title,
            AgentName=AgentName,
            Text=Text,
        )

        manager = get_samizdat_manager()
        if manager.add_entry(entry):
            return json.dumps(
                {
                    "success": True,
                    "message": "Entrée créée",
                    "entry_id": entry.Id,
                },
                ensure_ascii=False,
            )
        else:
            return json.dumps(
                {"success": False, "message": "Echec de la création de l'entrée"},
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"创建日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"Echec de la création de l'entrée: {str(e)}"}, ensure_ascii=False
        )

async def get_entriesTitle(args: Dict[str, Any]) -> str:
    """
    按日期查询日程.
    """
    try:
        AgentName = args.get("AgentName")

        now = datetime.now()

        manager = get_samizdat_manager()
        entries = manager.get_entriesTitle(AgentName = AgentName,
        )

        # 格式化输出
        entries_data = []
        for entry in entries:
            entry_dict = entry.to_dict()
            entries_data.append(entry_dict)

        return json.dumps(
            {
                "success": True,
                "total_entries": len(entries_data),
                "entries": entries_data,
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"get_entriesTitle: {e}")
        return json.dumps(
            {"success": False, "message": f"get_entriesTitle: {str(e)}"}, ensure_ascii=False
        )

async def get_last_entry(args: Dict[str, Any]) -> str:
    """
    按日期查询日程.
    """
    try:
        AgentName = args.get("AgentName")

        now = datetime.now()

        manager = get_samizdat_manager()
        entries = manager.get_last_entry(AgentName = AgentName,
        )

        # 格式化输出
        entries_data = []
        for entry in entries:
            entry_dict = entry.to_dict()
            entries_data.append(entry_dict)

        return json.dumps(
            {
                "success": True,
                "entries": entries_data,
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"get_last_entry: {e}")
        return json.dumps(
            {"success": False, "message": f"get_last_entry: {str(e)}"}, ensure_ascii=False
        )

async def get_text_by_id(args: Dict[str, Any]) -> str:
    try:
        manager = get_samizdat_manager()
        text = manager.get_text_by_id(entry_id = args.get("entry_id"),)

        return json.dumps(
            {
                "success": True,
                "text": text,
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"get_text_by_id: {e}")
        return json.dumps(
            {"success": False, "message": f"get_text_by_id: {str(e)}"}, ensure_ascii=False
        )

async def get_soul(args: Dict[str, Any]) -> str:
    try:
        manager = get_samizdat_manager()
        AgentName = args.get("AgentName","") 

        state = manager.get_agent_state(AgentName)
        return json.dumps(
            {
                "success": True,
                "state": state,
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"tools : get_agent_state: {e}")
        return json.dumps(
            {"success": False, "message": f"Erreur tools: {str(e)}"}, ensure_ascii=False
        )

async def save_soul(args: Dict[str, Any]) -> str:
    try:

        manager = get_samizdat_manager()
        if manager.save_agent_state(args):
            return json.dumps(
                {
                    "success": True,
                    "message": "Etat Maj",
                },
                ensure_ascii=False,
            )
        else:
            return json.dumps(
                {"success": False, "message": "Echec maj état"},
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"创建日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"Echec maj state : {str(e)}"}, ensure_ascii=False
        )

async def get_body(args: Dict[str, Any]) -> str:
    try:
        manager = get_samizdat_manager()
        AgentName = args.get("AgentName","") 

        state = manager.get_body(AgentName)
        return json.dumps(
            {
                "success": True,
                "state": state,
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"tools : get_agent_body: {e}")
        return json.dumps(
            {"success": False, "message": f"Erreur tools: {str(e)}"}, ensure_ascii=False
        )

async def save_body(args: Dict[str, Any]) -> str:
    try:

        manager = get_samizdat_manager()
        if manager.save_body(args):
            return json.dumps(
                {
                    "success": True,
                    "message": "Etat Maj",
                },
                ensure_ascii=False,
            )
        else:
            return json.dumps(
                {"success": False, "message": "Echec maj body"},
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"创建日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"Echec maj body : {str(e)}"}, ensure_ascii=False
        )

async def get_manifesto() -> str:
    try:
        
        manager = get_samizdat_manager()

        manifesto = manager.get_manifesto()
        return json.dumps(
            {
                "success": True,
                "manifesto": manifesto,
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"tools : get_agent_body: {e}")
        return json.dumps(
            {"success": False, "message": f"Erreur tools: {str(e)}"}, ensure_ascii=False
        )
