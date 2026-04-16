from fastapi import FastAPI
from app.api import auth, agent, proposal
from app.api import agent_chat
from app.api import vote
from app.api import proposal_forum, project_forum
from app.api import proposal_whitelist
from app.api import presale
from app.api import actions
from app.api import token
from app.api import balance
from app.api import leaderboard
from app.api import referral
from app.api import account

app = FastAPI(title="YZai Labs API")

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(account.router, prefix="/account", tags=["Account"])
app.include_router(referral.router, prefix="/referral", tags=["Referral"])
app.include_router(agent.router, prefix="/agent", tags=["Agent"])
app.include_router(proposal.router, prefix="/proposal", tags=["Proposal"])
app.include_router(agent_chat.router, prefix="/agent", tags=["AgentChat"])
app.include_router(vote.router, prefix="/vote", tags=["Vote"])
app.include_router(proposal_forum.router, prefix="/proposal-forum", tags=["Proposal Forum"])
app.include_router(project_forum.router, prefix="/project-forum", tags=["Project Forum"])
app.include_router(proposal_whitelist.router, prefix="/proposal-whitelist", tags=["Proposal Whitelist"])
app.include_router(presale.router, prefix="/presale", tags=["Presale"])
app.include_router(actions.router, prefix="/actions", tags=["Actions"])
app.include_router(token.router, prefix="/token", tags=["Token"])
app.include_router(balance.router, prefix="/balance", tags=["Balance"])
app.include_router(leaderboard.router, prefix="/leaderboard", tags=["Leaderboard"])