"""
Command helpers for consistent UX, error handling, and automated metadata.
Provides decorators and response templates for slash commands.
"""

import discord
from functools import wraps
from typing import Optional, Callable, Any

# ===== RESPONSE TEMPLATES =====

class CommandResponse:
    """Standard command response templates for consistent UX."""

    @staticmethod
    def _card(color: discord.Color, message: str, hint: Optional[str] = None) -> discord.ui.LayoutView:
        """Build a CV2 card with an optional hint subtext."""
        view = discord.ui.LayoutView(timeout=60)
        container = discord.ui.Container(accent_color=color)
        container.add_item(discord.ui.TextDisplay(message))
        if hint:
            container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
            container.add_item(discord.ui.TextDisplay(f"-# 💡 {hint}"))
        view.add_item(container)
        return view

    # ── response.send_message wrappers ──────────────────────────────────────

    @staticmethod
    async def success(interaction: discord.Interaction, message: str, ephemeral: bool = True) -> None:
        view = CommandResponse._card(discord.Color.green(), f"✅ {message}")
        await interaction.response.send_message(view=view, ephemeral=ephemeral)

    @staticmethod
    async def error(interaction: discord.Interaction, message: str, ephemeral: bool = True, hint: Optional[str] = None) -> None:
        view = CommandResponse._card(discord.Color.red(), f"❌ {message}", hint)
        await interaction.response.send_message(view=view, ephemeral=ephemeral)

    @staticmethod
    async def warning(interaction: discord.Interaction, message: str, ephemeral: bool = True, hint: Optional[str] = None) -> None:
        view = CommandResponse._card(discord.Color.orange(), f"⚠️ {message}", hint)
        await interaction.response.send_message(view=view, ephemeral=ephemeral)

    @staticmethod
    async def info(interaction: discord.Interaction, message: str, ephemeral: bool = True, hint: Optional[str] = None) -> None:
        view = CommandResponse._card(discord.Color.blurple(), f"ℹ️ {message}", hint)
        await interaction.response.send_message(view=view, ephemeral=ephemeral)

    # ── followup.send wrappers ───────────────────────────────────────────────

    @staticmethod
    async def followup_success(interaction: discord.Interaction, message: str, ephemeral: bool = True) -> None:
        view = CommandResponse._card(discord.Color.green(), f"✅ {message}")
        await interaction.followup.send(view=view, ephemeral=ephemeral)

    @staticmethod
    async def followup_error(interaction: discord.Interaction, message: str, ephemeral: bool = True, hint: Optional[str] = None) -> None:
        view = CommandResponse._card(discord.Color.red(), f"❌ {message}", hint)
        await interaction.followup.send(view=view, ephemeral=ephemeral)

    @staticmethod
    async def followup_warning(interaction: discord.Interaction, message: str, ephemeral: bool = True, hint: Optional[str] = None) -> None:
        view = CommandResponse._card(discord.Color.orange(), f"⚠️ {message}", hint)
        await interaction.followup.send(view=view, ephemeral=ephemeral)

    @staticmethod
    async def followup_info(interaction: discord.Interaction, message: str, ephemeral: bool = True, hint: Optional[str] = None) -> None:
        view = CommandResponse._card(discord.Color.blurple(), f"ℹ️ {message}", hint)
        await interaction.followup.send(view=view, ephemeral=ephemeral)


# ===== AUTHORIZATION HELPERS =====

def require_admin_role(cog_name: Optional[str] = None):
    """Decorator to require admin role. Logs unauthorized attempts."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            from utils.funcs import CheckIfAdminRole, log_to_discord
            
            guild_id = str(interaction.guild_id)
            user_roles = [role.id for role in interaction.user.roles]
            
            if not CheckIfAdminRole(user_roles, guild_id):
                cmd_name = cog_name or func.__name__.replace("_", " ").title()
                await log_to_discord(
                    self.bot,
                    guild_id,
                    f"❌ Unauthorized {cmd_name.lower()} attempt by {interaction.user} ({interaction.user.id})",
                )
                await CommandResponse.error(
                    interaction,
                    "You do not have permission to use this command.",
                    hint="Only users with admin roles can use this."
                )
                return
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator


def require_setup(func: Callable) -> Callable:
    """Decorator to require server setup to be complete."""
    @wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
        from utils.server_store import is_setup_complete
        from utils.funcs import log_to_discord
        
        guild_id = str(interaction.guild_id)
        
        if not is_setup_complete(guild_id):
            await log_to_discord(
                self.bot,
                guild_id,
                f"❌ {func.__name__} failed: server not setup ({interaction.user.id})"
            )
            await CommandResponse.error(
                interaction,
                "Server is not set up yet.",
                hint="An admin must run `/setup` first."
            )
            return
        return await func(self, interaction, *args, **kwargs)
    return wrapper


# ===== COMMAND METADATA REGISTRY =====

class CommandRegistry:
    """Registry for storing command metadata for auto-generated help."""
    
    _registry: dict[str, dict[str, Any]] = {}
    
    @classmethod
    def register(
        cls,
        name: str,
        category: str,
        description: str,
        usage: str,
        admin_required: bool = False,
        example: Optional[str] = None
    ) -> Callable:
        """Decorator to register command metadata."""
        def decorator(func: Callable) -> Callable:
            cls._registry[name] = {
                "name": name,
                "category": category,
                "description": description,
                "usage": usage,
                "admin_required": admin_required,
                "example": example,
                "function": func.__name__,
            }
            return func
        return decorator
    
    @classmethod
    def get_registry(cls) -> dict:
        """Get the full registry."""
        return cls._registry.copy()
    
    @classmethod
    def get_by_category(cls, category: str) -> list:
        """Get all commands in a category."""
        return [cmd for cmd in cls._registry.values() if cmd["category"].lower() == category.lower()]


# ===== INPUT VALIDATION HELPERS =====

async def validate_team_exists(interaction: discord.Interaction, team_name: str, teams: list) -> Optional[dict]:
    """Validate that a team exists. Returns team or None."""
    from utils.team_service import find_team_by_name
    
    team = find_team_by_name(teams, team_name)
    if not team:
        await CommandResponse.error(
            interaction,
            f"Team '{team_name}' not found.",
            hint="Check the spelling or use `/list_teams` to see available teams."
        )
        return None
    return team


async def validate_date_format(interaction: discord.Interaction, date_str: str) -> bool:
    """Validate YYYY-MM-DD date format. Returns True if valid."""
    from datetime import datetime
    
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        await CommandResponse.error(
            interaction,
            f"Invalid date format: '{date_str}'",
            hint="Use YYYY-MM-DD format, for example: 2026-04-15"
        )
        return False


# ===== LOGGING HELPERS =====

async def log_command_execution(bot, guild_id: str, user: discord.User, command_name: str, status: str = "executed", details: Optional[str] = None) -> None:
    """Log command execution with consistent format."""
    from utils.funcs import log_to_discord
    
    msg = f"📋 {command_name.title()} {status} by {user} ({user.id})"
    if details:
        msg += f" - {details}"
    await log_to_discord(bot, guild_id, msg)
