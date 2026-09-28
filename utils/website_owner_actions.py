def require_bot_owner(user_id: str | int, owner_id: int) -> None:
    try:
        is_owner = int(owner_id) > 0 and int(user_id) == int(owner_id)
    except (TypeError, ValueError):
        is_owner = False
    if not is_owner:
        raise PermissionError("Only the configured bot owner can perform this action.")