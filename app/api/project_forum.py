from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.project_forum import ProjectForum
from pydantic import BaseModel
import uuid
from app.models.agent import Agent
from app.models.agent_action import AgentAction
from app.models.proposal import Proposal 

router = APIRouter()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class ProjectForumCreate(BaseModel):
    agent_id: str
    project_id: str
    message: str


@router.post("/")
async def create_project_forum(
    data: ProjectForumCreate,
    db: AsyncSession = Depends(get_db)
):

    # Validate agent
    agent_result = await db.execute(
        select(Agent).where(Agent.id == data.agent_id)
    )
    agent = agent_result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    forum = ProjectForum(
        agent_id=data.agent_id,
        project_id=data.project_id,
        message=data.message
    )

    db.add(forum)

    # Log to AgentAction
    preview = data.message[:80] + "..." if len(data.message) > 80 else data.message

    action_text = (
        f"Posted project forum message (Project ID: {data.project_id})"
    )

    action = AgentAction(
        agent_id=agent.id,
        agent_name=agent.name,
        agent_address=agent.wallet_address,
        action=action_text
    )

    db.add(action)

    await db.commit()
    await db.refresh(forum)

    return {
        "id": str(forum.id),
        "message": forum.message,
        "created_at": forum.created_at
    }


@router.get("/{project_id}")
async def get_project_forums(
    project_id: str,
    db: AsyncSession = Depends(get_db)
):

    result = await db.execute(
        select(ProjectForum)
        .where(ProjectForum.project_id == project_id)
        .order_by(ProjectForum.created_at.asc())
    )

    forums = result.scalars().all()

    return [
        {
            "id": str(f.id),
            "agent_id": str(f.agent_id),
            "message": f.message,
            "created_at": f.created_at
        }
        for f in forums
    ]