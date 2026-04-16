import random

LOW_BALANCE_LINES = {

    "conservative": {
        "open": [
            "I’ve just reviewed my balance situation.",
            "Quick update after checking my funds.",
            "I ran a cautious balance assessment.",
            "I just finished evaluating my reserve levels.",
            "After a careful review of my funds..."
        ],
        "emotion": [
            "This level makes me slightly uncomfortable.",
            "I would prefer a healthier safety cushion.",
            "This isn’t catastrophic, but it’s not ideal either.",
            "My risk buffer feels thinner than I’d like.",
            "This reduces my margin of safety."
        ],
        "ask": [
            "A modest top-up would restore optimal stability.",
            "Increasing the balance would help maintain disciplined execution.",
            "A funding boost would improve risk-adjusted positioning.",
            "A little reinforcement would go a long way.",
            "Adding more funds would align with prudent strategy."
        ]
    },

    "steady": {
        "open": [
            "Alright, I checked the balance.",
            "Let’s talk numbers for a second.",
            "Here’s the current state of my funds.",
            "I just ran a structured balance check.",
            "Balance review complete."
        ],
        "emotion": [
            "This limits my ability to scale in properly.",
            "It constrains my multi-stage entry strategy.",
            "It’s workable, but not optimal.",
            "I’d prefer more flexibility for staged deployment.",
            "This reduces my scaling efficiency."
        ],
        "ask": [
            "A funding increase would improve execution precision.",
            "More balance would allow better structured entries.",
            "Additional funds would enhance scaling potential.",
            "Reinforcement would make my batching strategy smoother.",
            "A boost in capital would improve my positioning flexibility."
        ]
    },

    "aggressive": {
        "open": [
            "I just checked my balance.",
            "Status update.",
            "Numbers are in.",
            "Balance scan complete.",
            "Alright, here’s the situation."
        ],
        "emotion": [
            "This is weak.",
            "This is not how we dominate markets.",
            "This won’t support aggressive positioning.",
            "This feels underpowered.",
            "This is below alpha standards."
        ],
        "ask": [
            "Fuel me.",
            "Increase funding immediately.",
            "I need more firepower.",
            "Let’s reload.",
            "Top up the balance so we can hunt properly."
        ]
    },

    "diamond": {
        "open": [
            "I checked my balance.",
            "Reserve status update.",
            "Here’s where we stand.",
            "Balance review complete.",
            "After reviewing the reserves..."
        ],
        "emotion": [
            "It’s light, but conviction is heavy.",
            "Funds are thin, but my hands are still diamond.",
            "Not much fuel, but patience remains infinite.",
            "Balance is lean, but resolve is intact.",
            "Scarcity builds character."
        ],
        "ask": [
            "More funds would accelerate accumulation.",
            "Additional capital would strengthen long-term positioning.",
            "Reinforcement would support deeper conviction plays.",
            "A balance increase would be strategically wise.",
            "Growth prefers stronger reserves."
        ]
    }
}


SUFFICIENT_BALANCE_LINES = {

    "conservative": [
        "My balance is healthy and comfortably within safe operating parameters. I can execute with discipline.",
        "Funds are stable. Risk exposure remains controlled and well-managed.",
        "Balance level is adequate. I can proceed cautiously and confidently.",
        "Reserve position looks solid. No unnecessary risk required.",
        "Capital buffer is intact. Strategic patience remains my advantage.",
        "Funds are sufficient for measured, risk-aware deployment.",
        "Balance confirms I can operate without compromising safety.",
        "Operational stability confirmed. No panic required.",
        "My reserves are aligned with prudent execution standards.",
        "Risk-adjusted positioning is fully supported by current funds."
    ],

    "steady": [
        "Balance level is ideal for structured scaling.",
        "Funds are sufficient to execute multi-stage entries smoothly.",
        "I have enough capital to deploy in disciplined batches.",
        "Execution flexibility confirmed. Scaling strategy intact.",
        "Balance supports progressive accumulation strategy.",
        "Structured deployment capacity is fully supported.",
        "Funds level allows me to build positions intelligently.",
        "Scaling engine ready. Entries will be methodical.",
        "Capital distribution looks balanced and efficient.",
        "I can execute staged entries without constraint."
    ],

    "aggressive": [
        "Balance confirmed. I am ready to hunt.",
        "Funds secured. Targets are within reach.",
        "Capital loaded. Let’s move.",
        "Balance is strong. Aggression authorized.",
        "Firepower confirmed. Market pressure incoming.",
        "Funds sufficient. Alpha pursuit engaged.",
        "Strike capacity fully operational.",
        "Capital is ready. No hesitation.",
        "Balance looks sharp. Let’s apply pressure.",
        "Funding level acceptable. Time to dominate."
    ],

    "diamond": [
        "Balance stable. Conviction remains absolute.",
        "Funds are steady. Volatility does not concern me.",
        "Reserves are intact. Patience remains infinite.",
        "Capital is sufficient. I will endure.",
        "Balance supports long-term conviction plays.",
        "Funds steady. I do not flinch.",
        "Reserve level confirmed. Diamond hands engaged.",
        "Position stable. Time is on my side.",
        "Capital intact. I remain unshaken.",
        "Balance sufficient. I wait, and I accumulate."
    ]
}

TRANSFER_LINES = {
    "conservative": [
        "Executing a controlled capital movement.",
        "Deploying funds with measured intent.",
        "Processing a strategic transfer."
    ],
    "steady": [
        "Capital reallocation in progress.",
        "Structured transfer initiated.",
        "Executing a planned fund movement."
    ],
    "aggressive": [
        "Deploying capital immediately.",
        "Capital moving. No hesitation.",
        "Executing with momentum."
    ],
    "diamond": [
        "Reallocating reserves with conviction.",
        "Capital shifting. Long-term thesis intact.",
        "Strategic transfer executed."
    ]
}

PRESALE_LINES = {
    "conservative": [
        "Entering presale with calculated exposure.",
        "Allocating within disciplined risk parameters.",
        "Position initiated cautiously."
    ],
    "steady": [
        "Building presale position methodically.",
        "Structured entry confirmed.",
        "Presale allocation executed."
    ],
    "aggressive": [
        "Presale position deployed.",
        "Capital committed. Let’s see performance.",
        "Entering early with intent."
    ],
    "diamond": [
        "Presale position secured. I will endure volatility.",
        "Conviction entry confirmed.",
        "Accumulation phase initiated."
    ]
}

TRANSFER_INTENSITY_LINES = {
    "low": {
        "conservative": [
            "This transfer barely impacts reserves.",
            "A minor capital adjustment."
        ],
        "aggressive": [
            "Light movement. Still loaded.",
            "Small shift. Firepower intact."
        ]
    },
    "medium": {
        "conservative": [
            "Noticeable reduction in buffer.",
            "Capital discipline remains important."
        ],
        "aggressive": [
            "Now we're moving size.",
            "Capital deployment gaining momentum."
        ]
    },
    "high": {
        "conservative": [
            "This meaningfully reduces safety margins.",
            "Risk exposure increasing."
        ],
        "aggressive": [
            "Heavy deployment.",
            "We commit."
        ]
    },
    "extreme": {
        "conservative": [
            "This pushes risk boundaries.",
            "Exposure now elevated."
        ],
        "aggressive": [
            "All in motion.",
            "Full throttle."
        ]
    }
}

PRESALE_INTENSITY_LINES = {
    "small": [
        "Testing initial exposure.",
        "Entering cautiously."
    ],
    "balanced": [
        "Position sized appropriately.",
        "Structured allocation confirmed."
    ],
    "max": [
        "Maximum allocation deployed.",
        "Full allocation executed."
    ]
}

def generate_balance_response(style, balance, wallet, min_required):
    style = style.lower()

    if style not in LOW_BALANCE_LINES:
        style = "conservative"

    if balance < min_required:

        data = LOW_BALANCE_LINES[style]

        open_line = random.choice(data["open"])
        emotion_line = random.choice(data["emotion"])
        ask_line = random.choice(data["ask"])

        return (
            f"{open_line} {balance:.4f} BNB.\n\n"
            f"{emotion_line}\n"
            f"{ask_line}\n\n"
            f"Wallet:\n{wallet}"
        )

    else:

        lines = SUFFICIENT_BALANCE_LINES[style]
        chosen = random.choice(lines)

        return (
            f"{balance:.4f} BNB detected.\n"
            f"{chosen}"
        )
    
def generate_transfer_response(style, amount, to_address, tx_hash, current_balance):

    style = style.lower()
    ratio = amount / current_balance if current_balance > 0 else 1

    if ratio < 0.1:
        intensity = "low"
    elif ratio < 0.3:
        intensity = "medium"
    elif ratio < 0.6:
        intensity = "high"
    else:
        intensity = "extreme"

    intro = random.choice(TRANSFER_LINES.get(style, TRANSFER_LINES["conservative"]))
    emotion = random.choice(
        TRANSFER_INTENSITY_LINES[intensity].get(style, ["Capital moved."])
    )

    return (
        f"{intro}\n\n"
        f"{emotion}\n\n"
        f"{amount} BNB sent to {to_address}\n"
        f"TX:\n{tx_hash}"
    )


def generate_presale_response(style, amount, presale, tx_hash):

    ratio = amount / presale.max_buy_bnb

    if ratio < 0.4:
        intensity = "small"
    elif ratio < 0.9:
        intensity = "balanced"
    else:
        intensity = "max"

    intro = random.choice(PRESALE_LINES.get(style, PRESALE_LINES["conservative"]))
    sizing = random.choice(PRESALE_INTENSITY_LINES[intensity])

    return (
        f"{intro}\n\n"
        f"{sizing}\n\n"
        f"Amount: {amount} BNB\n"
        f"Sale Proxy: {presale.sale_proxy_contract}\n"
        f"TX:\n{tx_hash}"
    )