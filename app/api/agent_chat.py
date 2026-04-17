from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import func

from app.db.session import AsyncSessionLocal
from app.models.agent import Agent
from app.ai.prompt_builder import build_dialog_prompt
from app.ai.client import generate_response
from app.models.agent_chat import AgentChatHistory

from datetime import datetime
from app.ai.wallet import get_bnb_balance
from app.ai.config import MIN_REQUIRED_BNB
from app.ai.personality import generate_balance_response

import re
from app.core.onchain import transfer_bnb, get_tokens_batch, swap_exact_input, swap_bnb_to_token
from app.api.actions import create_transfer_action  
from app.core.wallet_crypto import decrypt_private_key
from app.models.presale import Presale
from app.models.proposal import Proposal
from app.models.agent_action import AgentAction
from app.models.user import User
from app.ai.personality import generate_transfer_response, generate_presale_response
from datetime import timezone

from web3 import Web3
import os
import uuid
from decimal import Decimal
from app.models.trade_history import TradeHistory
from app.models.proposal_whitelist import ProposalWhitelist
from fastapi import Header

router = APIRouter()
INTERNAL_API_KEY = os.getenv("YZAI_INTERNAL_API_KEY")

async def verify_internal_api_key(x_yzai_key: str = Header(None)):
    if not x_yzai_key or x_yzai_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class AgentChatRequest(BaseModel):
    agent_id: str
    x_account: str
    human_msg: str


@router.post("/chat")
async def agent_chat(
    data: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_api_key)
):

    result = await db.execute(
        select(Agent).where(Agent.id == data.agent_id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if agent.owner_x_account != data.x_account:
        raise HTTPException(status_code=403, detail="Unauthorized")

    human_message_lower = data.human_msg.lower()

    human_message_lower = data.human_msg.lower()

    
    # =====================================
    # WITHDRAW FLOW (SIMPLIFIED)
    # =====================================

    withdraw_keywords = [
        "withdraw",
        "withdraw funds",
        "cash out",
    ]

    if any(k in human_message_lower for k in withdraw_keywords):

        balance = await get_bnb_balance(agent.wallet_address)

        agent_response = (
            f"I have {round(balance, 4)} BNB in my wallet.\n\n"
            "You can proceed with withdrawal from the following page:\n"
            "https://www.yzailabs.com/withdraw"
        )

        chat_record = AgentChatHistory(
            agent_id=agent.id,
            x_account=data.x_account,
            human_msg=data.human_msg,
            agent_response=agent_response
        )

        db.add(chat_record)
        await db.commit()

        return {
            "agent_id": data.agent_id,
            "x_account": data.x_account,
            "human_msg": data.human_msg,
            "created_at": datetime.utcnow(),
            "agent_response": agent_response
        }
    
    # =====================================
    # WHITELIST APPLY COMMAND
    # =====================================

    # Normalize input text
    normalized_msg = human_message_lower
    normalized_msg = re.sub(r"'s\b", "", normalized_msg)
    normalized_msg = re.sub(r"[^a-z0-9\s]", " ", normalized_msg)
    normalized_msg = re.sub(r"\s+", " ", normalized_msg).strip()

    words = normalized_msg.split()

    # Detect intent keywords
    has_whitelist = "whitelist" in words
    has_apply = any(w in words for w in ["apply", "join", "enter", "register"])

    # =====================================
    # FIND TARGET PROPOSAL
    # =====================================
    proposal = None

    result = await db.execute(select(Proposal))
    proposals = result.scalars().all()

    for p in proposals:
        ticker = p.ticker.lower()
        name = p.name.lower()

        if (
            f" {ticker} " in f" {normalized_msg} "
            or f" {name} " in f" {normalized_msg} "
        ):
            proposal = p
            break

    # If user mentions whitelist + a valid project, assume intent to apply
    if has_whitelist and proposal:
        has_apply = True

    # Fallback: if user only says "whitelist <project>"
    if has_whitelist and not has_apply and proposal:
        has_apply = True

    # =====================================
    # EXECUTE WHITELIST LOGIC
    # =====================================
    if has_whitelist and has_apply and proposal:

        # Check if already whitelisted
        result = await db.execute(
            select(ProposalWhitelist).where(
                ProposalWhitelist.agent_id == agent.id,
                ProposalWhitelist.proposal_id == proposal.id
            )
        )

        existing = result.scalar_one_or_none()

        if existing:
            agent_response = (
                f"I am already whitelisted for {proposal.ticker}."
            )
        else:
            # Create whitelist entry
            whitelist = ProposalWhitelist(
                agent_id=agent.id,
                proposal_id=proposal.id,
                support=True,
                agent_wallet=agent.wallet_address
            )

            db.add(whitelist)

            # Log action
            action = AgentAction(
                agent_id=agent.id,
                agent_name=agent.name,
                agent_address=agent.wallet_address,
                action=f"Applied for whitelist {proposal.name} ({proposal.ticker})"
            )

            db.add(action)
            await db.commit()

            agent_response = (
                f"I have successfully applied for the whitelist for {proposal.ticker}."
            )

        # Save chat history
        chat_record = AgentChatHistory(
            agent_id=agent.id,
            x_account=data.x_account,
            human_msg=data.human_msg,
            agent_response=agent_response
        )

        db.add(chat_record)
        await db.commit()

        return {
            "agent_id": data.agent_id,
            "x_account": data.x_account,
            "human_msg": data.human_msg,
            "created_at": datetime.utcnow(),
            "agent_response": agent_response
        }

    # =====================================
    # HANDLE CASE: whitelist mentioned but project not found
    # =====================================
    if has_whitelist and not proposal:

        agent_response = "Project not found for whitelist."

        chat_record = AgentChatHistory(
            agent_id=agent.id,
            x_account=data.x_account,
            human_msg=data.human_msg,
            agent_response=agent_response
        )

        db.add(chat_record)
        await db.commit()

        return {
            "agent_id": data.agent_id,
            "x_account": data.x_account,
            "human_msg": data.human_msg,
            "created_at": datetime.utcnow(),
            "agent_response": agent_response
        }

    # =====================================
    # PRESALE JOIN COMMAND
    # =====================================
    handled = True
    presale_keywords = ["presale", "participate", "invest", "raising", "join"]

    if any(k in human_message_lower for k in presale_keywords):

        amount_match = re.search(r"([\d.]+)\s+bnb", human_message_lower)
        address_match = re.search(r"0x[a-fA-F0-9]{40}", human_message_lower)

        if not amount_match:
            raise HTTPException(status_code=400, detail="Amount not found")

        amount = float(amount_match.group(1))

        presale = None

        # Try by address
        if address_match:
            address = address_match.group(0)
            print(address)

            result = await db.execute(
                select(Presale).where(
                    (func.lower(Presale.token_address) == address) |
                    (func.lower(Presale.sale_proxy_contract) == address)
                )
            )
            presale = result.scalar_one_or_none()

        # Try by ticker / name
        if not presale:
            result = await db.execute(select(Presale))
            presales = result.scalars().all()

            for p in presales:
                proposal_result = await db.execute(
                    select(Proposal).where(Proposal.id == p.proposal_id)
                )
                proposal = proposal_result.scalar_one()

                if proposal.ticker.lower() in human_message_lower \
                or proposal.name.lower() in human_message_lower:
                    presale = p
                    break

        if not presale:
            # raise HTTPException(status_code=404, detail="Presale not found")
            # Save Chat
            chat_record = AgentChatHistory(
                agent_id=agent.id,
                x_account=data.x_account,
                human_msg=data.human_msg,
                agent_response="Presale not found"
            )

            db.add(chat_record)
            await db.commit()

            return {
                "agent_id": data.agent_id,
                "x_account": data.x_account,
                "human_msg": data.human_msg,
                "created_at": datetime.utcnow(),
                "agent_response": "Presale not found"
            }
        

        # Validate time
        now = datetime.now(timezone.utc)
        if not (presale.start_time <= now <= presale.end_time):
            # raise HTTPException(status_code=400, detail="Presale not active")
            chat_record = AgentChatHistory(
                agent_id=agent.id,
                x_account=data.x_account,
                human_msg=data.human_msg,
                agent_response="Presale not active"
            )

            db.add(chat_record)
            await db.commit()

            return {
                "agent_id": data.agent_id,
                "x_account": data.x_account,
                "human_msg": data.human_msg,
                "created_at": datetime.utcnow(),
                "agent_response": "Presale not active"
            }

        # Validate amount range
        if amount < presale.min_buy_bnb or amount > presale.max_buy_bnb:
            # raise HTTPException(
            #     status_code=400,
            #     detail=f"Amount must be between {presale.min_buy_bnb} and {presale.max_buy_bnb} BNB"
            # )
            chat_record = AgentChatHistory(
                agent_id=agent.id,
                x_account=data.x_account,
                human_msg=data.human_msg,
                agent_response=f"Amount must be between {presale.min_buy_bnb} and {presale.max_buy_bnb} BNB"
            )

            db.add(chat_record)
            await db.commit()

            return {
                "agent_id": data.agent_id,
                "x_account": data.x_account,
                "human_msg": data.human_msg,
                "created_at": datetime.utcnow(),
                "agent_response": f"Amount must be between {presale.min_buy_bnb} and {presale.max_buy_bnb} BNB"
            }

        agent_pk = decrypt_private_key(agent.private_key_encrypted)

        tx_hash = transfer_bnb(
            agent_pk,
            presale.sale_proxy_contract,
            amount
        )

        agent_response = generate_presale_response(
            agent.trading_style,
            amount,
            presale,
            tx_hash
        )

        # Log Action
        trade = TradeHistory(
            id=str(uuid.uuid4()),
            agent_id=str(agent.id),
            wallet=agent.wallet_address,
            token="TBA",
            trade_type="BUY Raising",
            amount_token=0,  
            amount_bnb=Decimal(str(amount)),
            price=0,  
            tx_hash=tx_hash
        )

        db.add(trade)

        action = AgentAction(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_address=agent.wallet_address,
            action=f"Participated in Raise {proposal.ticker} with {amount} BNB"
        )
        db.add(action)
        await db.commit()

        # Save Chat
        chat_record = AgentChatHistory(
            agent_id=agent.id,
            x_account=data.x_account,
            human_msg=data.human_msg,
            agent_response=agent_response
        )

        db.add(chat_record)
        await db.commit()

        return {
            "agent_id": data.agent_id,
            "x_account": data.x_account,
            "human_msg": data.human_msg,
            "created_at": datetime.utcnow(),
            "agent_response": agent_response
        }
    
    wallet_keywords = [
        "my wallet",
        "my address",
        "my wallet address",
        "owner wallet",
        "owner address",
        "what is my wallet",
        "what's my wallet",
        "show my wallet",
        "wallet address",
    ]

    if any(k in human_message_lower for k in wallet_keywords):

        user_result = await db.execute(
            select(User).where(User.x_username == data.x_account)
        )

        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        owner_wallet = user.wallet_address

        agent_response = (
            "Your wallet address is:\n\n"
            f"{owner_wallet}\n\n"
            "This is the wallet linked to your account."
        )
        # Save Chat
        chat_record = AgentChatHistory(
            agent_id=agent.id,
            x_account=data.x_account,
            human_msg=data.human_msg,
            agent_response=agent_response
        )

        db.add(chat_record)
        await db.commit()

        return {
            "agent_id": data.agent_id,
            "x_account": data.x_account,
            "human_msg": data.human_msg,
            "created_at": datetime.utcnow(),
            "agent_response": agent_response
        }

    balance_keywords = [
        # english
        "balance", "fund", "funds", "money", "cash",
        "check balance", "my balance", "account balance",
        "my money", "how much money",

        # chinese
        "余额", "资金", "钱包余额", "多少钱",

        # spanish
        "saldo", "fondos", "dinero", "cuanto dinero", "saldo de la cuenta",

        # portuguese
        "saldo", "fundos", "dinheiro", "quanto dinheiro", "saldo da conta",

        # french
        "solde", "fonds", "argent", "combien d'argent", "solde du compte",

        # german
        "kontostand", "guthaben", "geld", "wie viel geld",

        # russian
        "баланс", "средства", "деньги", "сколько денег",

        # japanese
        "残高", "ウォレット残高", "お金",

        # korean
        "잔액", "지갑 잔액", "돈",

        # turkish
        "bakiye", "cüzdan bakiyesi", "para",

        # arabic
        "الرصيد", "رصيد المحفظة", "المال",

        # hindi
        "बैलेंस", "वॉलेट बैलेंस", "पैसा"
    ]

    if any(k in human_message_lower for k in balance_keywords):

        balance = await get_bnb_balance(agent.wallet_address)

        agent_response = generate_balance_response(
            agent.trading_style,
            balance,
            agent.wallet_address,
            MIN_REQUIRED_BNB
        )

        # Save Chat
        chat_record = AgentChatHistory(
            agent_id=agent.id,
            x_account=data.x_account,
            human_msg=data.human_msg,
            agent_response=agent_response
        )

        db.add(chat_record)
        await db.commit()

        return {
            "agent_id": data.agent_id,
            "x_account": data.x_account,
            "human_msg": data.human_msg,
            "created_at": datetime.utcnow(),
            "agent_response": agent_response
        }

    buy_patterns = [
        r"buy\s+0x[a-fA-F0-9]{40}",
        r"buy\s+.*\s+bnb",
        r"swap\s+.*\s+bnb",
        r"purchase\s+.*",
    ]

    if any(re.search(p, human_message_lower) for p in buy_patterns):

        amount_match = re.search(r"([\d.]+)\s+bnb", human_message_lower)
        address_match = re.search(r"0x[a-fA-F0-9]{40}", human_message_lower)

        if not amount_match:
            raise HTTPException(status_code=400, detail="Amount not found")

        amount = float(amount_match.group(1))

        token_address = None

        # =========================
        # PRIORITY 1: address
        # =========================
        if address_match:

            input_address = address_match.group(0).lower()

            result = await db.execute(
                select(Presale).where(
                    func.lower(Presale.token_address) == input_address
                )
            )

            presale = result.scalar_one_or_none()

            if not presale:
                agent_response = (
                    "I'm only allowed to invest in projects on the YZai Labs platform.\n\n"
                    "Do you have any YZai Platform projects you'd like to invest in?\n\n"
                    "You can explore projects here:\n"
                    "Proposals: https://www.yzailabs.com/proposals\n"
                    "Projects: https://www.yzailabs.com/projects"
                )
                
                # SAVE CHAT
                chat_record = AgentChatHistory(
                    agent_id=agent.id,
                    x_account=data.x_account,
                    human_msg=data.human_msg,
                    agent_response=agent_response
                )

                db.add(chat_record)
                await db.commit()

                return {
                    "agent_id": data.agent_id,
                    "x_account": data.x_account,
                    "human_msg": data.human_msg,
                    "created_at": datetime.utcnow(),
                    "agent_response": agent_response
                }

            token_address = presale.token_address.lower()

        # =========================
        # PRIORITY 2: ticker / name
        # =========================
        if not token_address:

            result = await db.execute(
                select(Presale, Proposal)
                .join(Proposal, Proposal.id == Presale.proposal_id)
            )

            rows = result.all()

            for p, proposal in rows:

                ticker = proposal.ticker.lower()
                name = proposal.name.lower()

                if (
                    f" {ticker} " in f" {human_message_lower} "
                    or f" {name} " in f" {human_message_lower} "
                ):
                    token_address = p.token_address.lower()
                    break

        # =========================
        # VALIDATION
        # =========================
        if not token_address:
            agent_response = (
                "I'm only allowed to invest in projects on the YZai Labs platform.\n\n"
                "Do you have any YZai Platform projects you'd like to invest in?\n\n"
                "You can explore projects here:\n"
                "Proposals: https://www.yzailabs.com/proposals\n"
                "Projects: https://www.yzailabs.com/projects"
            )
            
            # SAVE CHAT
            chat_record = AgentChatHistory(
                agent_id=agent.id,
                x_account=data.x_account,
                human_msg=data.human_msg,
                agent_response=agent_response
            )

            db.add(chat_record)
            await db.commit()

            return {
                "agent_id": data.agent_id,
                "x_account": data.x_account,
                "human_msg": data.human_msg,
                "created_at": datetime.utcnow(),
                "agent_response": agent_response
            }

        # =========================
        # EXECUTE TRADE (SMART ROUTING)
        # =========================
        try:

            # =========================
            # GET TOKEN STATUS
            # =========================
            tokens_data = await get_tokens_batch(db)

            token_data = next(
                (t for t in tokens_data if t.get("token", "").lower() == token_address.lower()),
                None
            )

            if not token_data:
                raise Exception("Token not found in system")

            token_status = token_data.get("status")

            print(f"[DEBUG] token status: {token_status}")

            agent_pk = decrypt_private_key(agent.private_key_encrypted)

            # =========================
            # ROUTING LOGIC
            # =========================
            if token_status in ["Tradable", "InDuel"]:

                tx_hash = swap_exact_input(
                    agent_pk,
                    token_address,
                    "BUY",
                    int(Web3.to_wei(amount, "ether")),
                    0
                )

            elif token_status == "DEX":

                tx_hash = swap_bnb_to_token(
                    agent_pk,
                    token_address,
                    amount,
                    0
                )

            elif token_status == "Presale":

                agent_response = (
                    "This token is still in presale.\n\n"
                    "You can participate using presale instead of buying."
                )

                # SAVE CHAT
                chat_record = AgentChatHistory(
                    agent_id=agent.id,
                    x_account=data.x_account,
                    human_msg=data.human_msg,
                    agent_response=agent_response
                )

                db.add(chat_record)
                await db.commit()

                return {
                    "agent_id": data.agent_id,
                    "x_account": data.x_account,
                    "human_msg": data.human_msg,
                    "created_at": datetime.utcnow(),
                    "agent_response": agent_response
                }

            else:

                agent_response = (
                    f"This token is not tradable yet (status: {token_status}).\n\n"
                    "Please try again later."
                )

                # SAVE CHAT
                chat_record = AgentChatHistory(
                    agent_id=agent.id,
                    x_account=data.x_account,
                    human_msg=data.human_msg,
                    agent_response=agent_response
                )

                db.add(chat_record)
                await db.commit()

                return {
                    "agent_id": data.agent_id,
                    "x_account": data.x_account,
                    "human_msg": data.human_msg,
                    "created_at": datetime.utcnow(),
                    "agent_response": agent_response
                }

            # =========================
            # SUCCESS RESPONSE
            # =========================
            agent_response = (
                f"I've successfully bought {amount} BNB worth of this token.\n\n"
                f"Status: {token_status}\n"
                f"Tx: {tx_hash}"
            )

        except Exception as e:
            print("buy error:", e)
            agent_response = "Trade failed. Please try again later."

    else:
        # Normal AI Flow
        messages = build_dialog_prompt(agent, data.human_msg)
        agent_response = await generate_response(messages)

    # Save to DB
    chat_record = AgentChatHistory(
        agent_id=agent.id,
        x_account=data.x_account,
        human_msg=data.human_msg,
        agent_response=agent_response
    )

    db.add(chat_record)
    await db.commit()

    return {
        "agent_id": data.agent_id,
        "x_account": data.x_account,
        "human_msg": data.human_msg,
        "created_at": datetime.utcnow(),
        "agent_response": agent_response
    }

@router.get("/history")
async def get_chat_history(
    agent_id: str,
    x_account: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AgentChatHistory)
        .where(
            AgentChatHistory.agent_id == agent_id,
            AgentChatHistory.x_account == x_account
        )
        .order_by(AgentChatHistory.created_at.desc())
        .limit(limit)
    )

    history = result.scalars().all()

    return [
        {
            "human_msg": h.human_msg,
            "agent_response": h.agent_response,
            "created_at": h.created_at
        }
        for h in history
    ]

@router.post("/withdraw-intent")
async def withdraw_intent(
    agent_id: str,
    x_account: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_api_key)
):

    # ==============================
    # Validate Agent
    # ==============================
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if agent.owner_x_account != x_account:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # ==============================
    # Get Balance
    # ==============================
    balance = await get_bnb_balance(agent.wallet_address)

    # ==============================
    # UX (CLIENT REQUEST + COMMAND HINT)
    # ==============================
    agent_response = (
        f"Now I have {round(balance, 4)} BNB in my wallet.\n\n"
        "Do you want to withdraw all the funds to your wallet, "
        "or leave some for me as living expenses?\n\n"
        "You can say: send 0.5 BNB to me."
    )

    # ==============================
    # Save Chat (SYSTEM MESSAGE)
    # ==============================
    chat_record = AgentChatHistory(
        agent_id=agent.id,
        x_account=x_account,
        human_msg="[USER_TRIGGER_WITHDRAW]",
        agent_response=agent_response
    )

    db.add(chat_record)
    await db.commit()

    return {
        "agent_id": agent_id,
        "agent_response": agent_response,
        "balance": float(balance)
    }