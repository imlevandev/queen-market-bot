import asyncio
import json
import os
import sys
import time
from datetime import datetime

# Đảm bảo mã hóa console là UTF-8 trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from market_data import MarketManager
from updater import auto_update_check, get_base_dir
from version import VERSION

BASE_DIR = get_base_dir()
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
market = MarketManager(CONFIG_FILE)

def make_progress_bar(ratio, length=10):
    filled = max(0, min(length, int(round(length * ratio / 100))))
    bar = "█" * filled + "░" * (length - filled)
    return f"`[{bar}]` **{ratio:.1f}%**"

def format_item_card(item):
    """Định dạng cực kỳ gọn gàng, rõ ràng, không màu mè"""
    ratio = item["Ratio"]
    p = item["Price"]
    m = item["Max"]
    lbl = item["Label"]

    if ratio >= 100:
        header = f"🚨 **[CHẠM MAX 100%] {lbl}**"
    elif ratio >= 80:
        header = f"🔥 **[SÁT MAX - {ratio:.1f}%] {lbl}**"
    else:
        header = f"🏷️ **{lbl}**"

    return (
        f"{header}\n"
        f"• Giá hiện tại: **{p:,}$**\n"
        f"• Giá MAX: **{m:,}$**\n"
        f"• Tiến độ MAX: {make_progress_bar(ratio)}"
    )

def format_max_list(items):
    matched = [it for it in items if it.get("Ratio", 0) >= 80]
    matched.sort(key=lambda x: x["Ratio"], reverse=True)
    if matched:
        lines = ["🔥 **DANH SÁCH MÓN TỪ 80% ĐẾN 100% MAX:**"]
        for it in matched:
            icon = "🚨" if it["Ratio"] >= 100 else "⚡"
            lines.append(f"{icon} **{it['Label']}**: {it['Price']:,}$ / {it['Max']:,}$ — {make_progress_bar(it['Ratio'], 8)}")
        return "\n".join(lines)
    else:
        top_items = sorted(items, key=lambda x: x.get("Ratio", 0), reverse=True)[:5]
        lines = ["⚠️ **Chưa có món nào đạt mốc 80% MAX.**\n📊 **Top các món gần MAX nhất hiện tại:**"]
        for it in top_items:
            lines.append(f"• **{it['Label']}**: {it['Price']:,}$ / {it['Max']:,}$ — {make_progress_bar(it['Ratio'], 8)}")
        return "\n".join(lines)

async def send_webhook_alert(webhook_url, content):
    """Gửi cảnh báo qua Discord Webhook nếu cấu hình webhook"""
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(webhook_url, json={"content": content}, timeout=5)
    except Exception as e:
        print(f"[!] Lỗi gửi Webhook: {e}")

# ==================== DISCORD BOT CLIENT ====================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print("=" * 60)
    print(f"[+] Bot đã kết nối thành công: {bot.user} (ID: {bot.user.id})")
    print(f"[+] Phiên bản: v{VERSION}")
    print(f"[+] Số máy chủ đang tham gia: {len(bot.guilds)}")
    print(f"[+] Chế độ: THÔNG BÁO TỪ 80% ĐẾN 100% MAX")
    print(f"[+] Chu kỳ quét thị trường: {market.config.get('check_interval_seconds', 30)}s")
    print("=" * 60, flush=True)

    try:
        synced = await bot.tree.sync()
        print(f"[+] Đã đồng bộ {len(synced)} lệnh Slash (/) thành công.", flush=True)
    except Exception as e:
        print(f"[!] Lỗi đồng bộ Slash Command: {e}", flush=True)

    # Khởi động tác vụ quét giá định kỳ
    if not auto_price_monitor.is_running():
        auto_price_monitor.start()

    # Gửi thông báo chào mừng vào kênh chỉ định nếu có
    ch_id = market.config.get("channel_id")
    if ch_id:
        try:
            ch_int = int(ch_id)
            ch = bot.get_channel(ch_int)
            if not ch:
                ch = await bot.fetch_channel(ch_int)
            if ch:
                await ch.send("🟢 **Bot báo giá đã hoạt động!** (Tự động thông báo khi giá đạt từ **80% đến 100% MAX**)")
                print(f"[+] Đã thông báo bot hoạt động tới kênh: #{getattr(ch, 'name', ch_id)}", flush=True)
        except Exception as e:
            print(f"[!] Không thể gửi vào channel: {e}", flush=True)

# Tác vụ chạy ngầm kiểm tra giá định kỳ (THÔNG BÁO TỪ 80% - 100% MAX)
@tasks.loop(seconds=market.config.get("check_interval_seconds", 30))
async def auto_price_monitor():
    try:
        alerts = market.check_for_alerts()
        if not alerts:
            return

        channel_id = market.config.get("channel_id")
        webhook_url = market.config.get("webhook_url")
        role_id = market.config.get("ping_role_id")

        print(f"[*] [{datetime.now().strftime('%H:%M:%S')}] Phát hiện {len(alerts)} món từ 80% - 100% MAX!", flush=True)

        if len(alerts) > 3:
            # Gộp thành 1 danh sách gọn gàng nếu nhiều món cùng lúc
            lines = [f"🔥 **THÔNG BÁO THỊ TRƯỜNG ({len(alerts)} món đạt 80% - 100% MAX):**"]
            for it in alerts:
                icon = "🚨" if it["Ratio"] >= 100 else "⚡"
                lines.append(f"{icon} **{it['Label']}**: {it['Price']:,}$ / {it['Max']:,}$ — {make_progress_bar(it['Ratio'], 8)}")
            summary_msg = "\n".join(lines)

            if channel_id:
                try:
                    ch_int = int(channel_id)
                    target_ch = bot.get_channel(ch_int) or await bot.fetch_channel(ch_int)
                    if target_ch:
                        await target_ch.send(summary_msg)
                except Exception as e:
                    print(f"[!] Lỗi gửi vào channel {channel_id}: {e}", flush=True)

            if webhook_url:
                await send_webhook_alert(webhook_url, content=summary_msg)
        else:
            # Gửi từng thẻ gọn gàng nếu chỉ có 1-3 món
            for it in alerts:
                msg = format_item_card(it)
                if role_id and it["Ratio"] >= 100:
                    msg = f"<@&{role_id}>\n" + msg

                if channel_id:
                    try:
                        ch_int = int(channel_id)
                        target_ch = bot.get_channel(ch_int) or await bot.fetch_channel(ch_int)
                        if target_ch:
                            await target_ch.send(msg)
                    except Exception as e:
                        print(f"[!] Lỗi gửi vào channel {channel_id}: {e}", flush=True)

                if webhook_url:
                    await send_webhook_alert(webhook_url, content=msg)

                await asyncio.sleep(0.5)

    except Exception as e:
        print(f"[!] Lỗi trong auto_price_monitor: {e}", flush=True)

# ==================== CÁC LỆNH DISCORD (PREFIX !) ====================

@bot.command(name="gia", aliases=["g", "price", "checkgia"])
async def cmd_gia(ctx, *, item_name: str = None):
    """Tra cứu giá của một vật phẩm (VD: !gia sắt, !gia nấm)"""
    if not item_name:
        await ctx.send("⚠️ **Cú pháp:** `!gia <tên vật phẩm>`\n*Ví dụ:* `!gia sắt`, `!gia nấm`, `!gia bột mì`, `!gia vàng`")
        return

    matches = market.search_items(item_name)
    if not matches:
        await ctx.send(f"❌ Không tìm thấy: **{item_name}**")
        return

    if len(matches) == 1:
        await ctx.send(format_item_card(matches[0]))
    else:
        if len(matches) > 10:
            matches = matches[:10]
        lines = [f"🔍 **Kết quả tìm kiếm '{item_name}':**"]
        for it in matches:
            lines.append(f"• **{it['Label']}**: {it['Price']:,}$ / {it['Max']:,}$ — {make_progress_bar(it['Ratio'], 6)}")
        await ctx.send("\n".join(lines))

@bot.command(name="max", aliases=["satmax", "dinh"])
async def cmd_max(ctx):
    """Xem danh sách các mặt hàng đã chạm max"""
    items = market.get_all_items()
    await ctx.send(format_max_list(items))

@bot.command(name="check", aliases=["kiemtra", "scan"])
async def cmd_check(ctx):
    """Quét dữ liệu mới nhất từ FiveM hoặc file"""
    market.update()
    items = market.get_all_items()
    await ctx.send("🔄 **Đã cập nhật thị trường!**\n" + format_max_list(items))

@bot.command(name="kenh", aliases=["setchannel"])
@commands.has_permissions(administrator=True)
async def cmd_setchannel(ctx):
    """Đặt kênh hiện tại làm nơi nhận thông báo giá tự động"""
    ch_id = str(ctx.channel.id)
    market.config["channel_id"] = ch_id
    market.save_config()
    await ctx.send(f"✅ Đã đặt kênh <#{ch_id}> làm kênh nhận **Thông Báo Khi Chạm Max**!")

@bot.command(name="help", aliases=["trogiup", "lenh"])
async def cmd_help(ctx):
    """Xem danh sách hướng dẫn lệnh"""
    help_text = (
        "🤖 **LỆNH BOT BÁO GIÁ:**\n"
        "• `!gia <tên>` (hoặc `/gia`): Tra giá 1 món (VD: `!gia sắt`, `!gia nấm`)\n"
        "• `!max` (hoặc `/max`): Xem các món đã chạm MAX hoặc gần MAX nhất\n"
        "• `!check` (hoặc `/kiemtra`): Quét và cập nhật giá mới nhất ngay lập tức\n"
        "• `!kenh`: *(Admin)* Đặt kênh nhận thông báo tự động"
    )
    await ctx.send(help_text)

# ==================== SLASH COMMANDS (/) ====================

@bot.tree.command(name="gia", description="Tra cứu giá vật phẩm (VD: sat, vang, nam dui ga)")
@app_commands.describe(ten_vat_pham="Tên vật phẩm cần tra")
async def slash_gia(interaction: discord.Interaction, ten_vat_pham: str):
    matches = market.search_items(ten_vat_pham)
    if not matches:
        await interaction.response.send_message(f"❌ Không tìm thấy: **{ten_vat_pham}**", ephemeral=True)
        return

    if len(matches) == 1:
        await interaction.response.send_message(format_item_card(matches[0]))
    else:
        if len(matches) > 10:
            matches = matches[:10]
        lines = [f"🔍 **Kết quả tìm kiếm '{ten_vat_pham}':**"]
        for it in matches:
            lines.append(f"• **{it['Label']}**: {it['Price']:,}$ / {it['Max']:,}$ — {make_progress_bar(it['Ratio'], 6)}")
        await interaction.response.send_message("\n".join(lines))

@bot.tree.command(name="max", description="Xem các mặt hàng đã chạm max")
async def slash_max(interaction: discord.Interaction):
    items = market.get_all_items()
    await interaction.response.send_message(format_max_list(items))

@bot.tree.command(name="kiemtra", description="Kiểm tra thị trường ngay lập tức")
async def slash_check(interaction: discord.Interaction):
    market.update()
    items = market.get_all_items()
    await interaction.response.send_message("🔄 **Đã cập nhật thị trường!**\n" + format_max_list(items))

def main():
    # 1. Kiểm tra và tự động cập nhật nếu có bản mới trên GitHub
    if auto_update_check():
        return

    cfg = market.config
    bot_token = cfg.get("bot_token", "").strip()

    if bot_token:
        try:
            print("[+] Đang khởi động Discord Bot...", flush=True)
            bot.run(bot_token)
        except Exception as e:
            print(f"\n❌ Lỗi khi khởi động Bot: {e}", flush=True)
    else:
        print("[!] Chưa có bot_token trong file config.json!", flush=True)
        input("\nNhấn Enter để thoát...")

if __name__ == "__main__":
    main()
