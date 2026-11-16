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

def get_cat_tag_and_icon(cat):
    if cat == "lumberjack":
        return "🪓 [GỖ]", "🪓"
    elif cat == "mining":
        return "⛏️ [ĐÁ/QUẶNG]", "⛏️"
    elif cat == "fishing":
        return "🎣 [CÁ]", "🎣"
    elif cat == "farming":
        return "🌾 [NÔNG SẢN]", "🌾"
    elif cat in ("mushroom", "mushrooms"):
        return "🍄 [NẤM]", "🍄"
    elif cat == "materials":
        return "🧱 [VẬT LIỆU]", "🧱"
    return f"📦 [{str(cat).upper()}]", "📦"

def format_item_card(item):
    """Định dạng cực kỳ gọn gàng, rõ ràng, có phân biệt từng nghề, buff và cảnh báo tụt giá"""
    alert_type = item.get("alert_type", "")
    ratio = item["Ratio"]
    p = item["Price"]
    m = item["Max"]
    lbl = item["Label"]
    cat = item.get("category", "")
    cat_pct = item.get("CategoryPercent", 0)
    cat_tag, _ = get_cat_tag_and_icon(cat)
    buff_str = f" *(Buff +{int(cat_pct)}%)*" if cat_pct > 0 else ""

    if alert_type == "PRICE_DROP":
        diff = item.get("price_diff", 0)
        prev_p = item.get("prev_price", p)
        return (
            f"📉 **[CẢNH BÁO TỤT GIÁ] {cat_tag} {lbl}**\n"
            f"• Vừa giảm: **{prev_p:,}$** ➔ **{p:,}$** (`{diff:+,}$`)\n"
            f"• Giá MAX: **{m:,}$**{buff_str}\n"
            f"• Tiến độ MAX: {make_progress_bar(ratio)}\n"
            f"*(Chú ý: Giá đang hạ nhiệt sau khi bán, cân nhắc dừng xả nếu giá xuống thấp)*"
        )
    elif alert_type == "DROP_BELOW_80":
        diff = item.get("price_diff", 0)
        prev_p = item.get("prev_price", p)
        return (
            f"⚠️ **[NGỪNG XẢ HÀNG - TỤT DƯỚI 80%] {cat_tag} {lbl}**\n"
            f"• Vừa tụt khỏi mốc ngon: **{prev_p:,}$** ➔ **{p:,}$** (`{diff:+,}$`)\n"
            f"• Tiến độ hiện tại: {make_progress_bar(ratio)} *(< 80%)*\n"
            f"*(Khuyên: Ngừng bán để chờ giá tích lũy hồi phục lại)*"
        )
    elif ratio >= 100:
        header = f"🚨 **[CHẠM MAX 100%] {cat_tag} {lbl}**"
    elif ratio >= 80:
        header = f"🔥 **[SÁT MAX - {ratio:.1f}%] {cat_tag} {lbl}**"
    else:
        header = f"🏷️ **{cat_tag} {lbl}**"

    return (
        f"{header}\n"
        f"• Giá bán hiện tại: **{p:,}$**{buff_str}\n"
        f"• Giá MAX: **{m:,}$**\n"
        f"• Tiến độ MAX: {make_progress_bar(ratio)}"
    )

def format_category_table(category_key, title, icon, items):
    cat_items = [it for it in items if it.get("category") == category_key or (category_key == "mushrooms" and it.get("category") == "mushroom")]
    cat_items.sort(key=lambda x: x["Ratio"], reverse=True)
    if not cat_items:
        return [f"⚠️ Không có vật phẩm nào thuộc danh mục **{title}**."]

    header = f"{icon} **BẢNG GIÁ THỊ TRƯỜNG {title.upper()} ({len(cat_items)} VẬT PHẨM BÁN ĐƯỢC):**"
    chunks = []
    current_lines = [header]
    current_len = len(header)

    for it in cat_items:
        r = it["Ratio"]
        badge = "🚨" if r >= 100 else ("⚡" if r >= 80 else "🔹")
        cat_pct = it.get("CategoryPercent", 0)
        buff_str = f" *(+{int(cat_pct)}% Buff)*" if cat_pct > 0 else ""
        trend = "📈" if it.get("Status") == "up" else ("📉" if it.get("Status") == "down" else "➖")
        line = f"{badge} **{it['Label']}**: **{it['Price']:,}$** / Max {it['Max']:,}${buff_str} | {trend} — {make_progress_bar(r, 6)}"

        if current_len + len(line) + 2 > 1900:
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_len = len(line)
        else:
            current_lines.append(line)
            current_len += len(line) + 1

    if current_lines:
        chunks.append("\n".join(current_lines))
    return chunks

def format_all_categories_table(items):
    cat_order = [
        ("lumberjack", "Nghề Gỗ (Lumberjack)", "🪓"),
        ("mining", "Nghề Đá & Khoáng Sản (Mining)", "⛏️"),
        ("fishing", "Nghề Đánh Bắt Cá & Hải Sản (Fishing)", "🎣"),
        ("farming", "Nghề Nông Sản & Trồng Trọt (Farming)", "🌾"),
        ("mushrooms", "Nghề Hái Nấm (Mushrooms)", "🍄"),
        ("materials", "Vật Liệu & Chế Tạo (Materials)", "🧱"),
    ]
    all_chunks = []
    total_count = len(items)
    header = f"📊 **BẢNG GIÁ TOÀN BỘ THỊ TRƯỜNG QUEEN MARKET ({total_count} MẶT HÀNG):**"
    current_lines = [header]
    current_len = len(header)

    for cat_key, title, icon in cat_order:
        cat_items = [it for it in items if it.get("category") == cat_key or (cat_key == "mushrooms" and it.get("category") == "mushroom")]
        if not cat_items:
            continue
        cat_items.sort(key=lambda x: x["Ratio"], reverse=True)
        cat_header = f"\n{icon} **{title.upper()} ({len(cat_items)} MÓN):**"
        
        if current_len + len(cat_header) > 1850:
            all_chunks.append("\n".join(current_lines))
            current_lines = [cat_header]
            current_len = len(cat_header)
        else:
            current_lines.append(cat_header)
            current_len += len(cat_header) + 1

        for it in cat_items:
            r = it["Ratio"]
            badge = "🚨" if r >= 100 else ("⚡" if r >= 80 else "🔹")
            cat_pct = it.get("CategoryPercent", 0)
            buff_str = f" *(+{int(cat_pct)}% Buff)*" if cat_pct > 0 else ""
            trend = "📈" if it.get("Status") == "up" else ("📉" if it.get("Status") == "down" else "➖")
            line = f"{badge} **{it['Label']}**: **{it['Price']:,}$** / Max {it['Max']:,}${buff_str} | {trend} — {make_progress_bar(r, 6)}"

            if current_len + len(line) + 2 > 1850:
                all_chunks.append("\n".join(current_lines))
                current_lines = [line]
                current_len = len(line)
            else:
                current_lines.append(line)
                current_len += len(line) + 1

    if current_lines:
        all_chunks.append("\n".join(current_lines))
    return all_chunks

def format_max_list(items, enabled_cats=None):
    if enabled_cats and "all" not in enabled_cats:
        items = [it for it in items if it.get("category") in enabled_cats]

    matched = [it for it in items if it.get("Ratio", 0) >= 80]
    matched.sort(key=lambda x: x["Ratio"], reverse=True)
    if matched:
        lines = [f"🔥 **DANH SÁCH MẶT HÀNG TỪ 80% ĐẾN 100% MAX ({len(matched)} MÓN):**"]
        for it in matched:
            icon = "🚨" if it["Ratio"] >= 100 else "⚡"
            cat = it.get("category")
            _, cat_icon = get_cat_tag_and_icon(cat)
            cat_pct = it.get("CategoryPercent", 0)
            buff_str = f" *(+{int(cat_pct)}% Buff)*" if cat_pct > 0 else ""
            lines.append(f"{icon} {cat_icon} **{it['Label']}**: {it['Price']:,}$ / {it['Max']:,}${buff_str} — {make_progress_bar(it['Ratio'], 8)}")
        return "\n".join(lines)
    else:
        top_items = sorted(items, key=lambda x: x.get("Ratio", 0), reverse=True)[:8]
        lines = ["⚠️ **Chưa có mặt hàng nào đạt mốc 80% MAX.**\n📊 **Top các món gần MAX nhất thị trường hiện tại:**"]
        for it in top_items:
            cat = it.get("category")
            _, cat_icon = get_cat_tag_and_icon(cat)
            cat_pct = it.get("CategoryPercent", 0)
            buff_str = f" *(+{int(cat_pct)}% Buff)*" if cat_pct > 0 else ""
            lines.append(f"• {cat_icon} **{it['Label']}**: {it['Price']:,}$ / {it['Max']:,}${buff_str} — {make_progress_bar(it['Ratio'], 8)}")
        return "\n".join(lines)

def format_live_dashboard(market):
    """Định dạng Bảng Điện Tử Thị Trường Live (Realtime tự động nhảy số)"""
    items = market.get_all_items()
    now_str = datetime.now().strftime("%H:%M:%S")
    rem_sec = getattr(market, "remaining_seconds", 0)
    if rem_sec > 0:
        mins = rem_sec // 60
        secs = rem_sec % 60
        timer_str = f"⏱️ **Đổi giá sau:** `{mins:02d}m {secs:02d}s`"
    else:
        timer_str = "⏱️ **Đổi giá:** `Đang cập nhật...`"

    src_label = "🟢 **FiveM Realtime**" if "FiveM" in market.active_source else f"📁 **Offline ({market.active_source})**"

    # 1. Các món chạm đỉnh MAX (>= 100%)
    max_items = [it for it in items if it.get("Ratio", 0) >= 100]
    max_items.sort(key=lambda x: x["Price"], reverse=True)

    # 2. Các món sát MAX (80% -> 99%)
    near_items = [it for it in items if 80 <= it.get("Ratio", 0) < 100]
    near_items.sort(key=lambda x: x["Ratio"], reverse=True)

    lines = [
        "╔══════════════════════════════════════════╗",
        "║ 📊 **BẢNG ĐIỆN TỬ THỊ TRƯỜNG CHỢ LIVE (REALTIME)** ║",
        "╚══════════════════════════════════════════╝",
        f"{src_label} | {timer_str} | 🕒 `{now_str}`",
        ""
    ]

    if max_items:
        lines.append(f"🚨 **ĐÃ CHẠM ĐỈNH MAX 100% ({len(max_items)} món) — BÁN NGAY KẺO TỤT:**")
        for it in max_items[:6]:
            _, c_icon = get_cat_tag_and_icon(it.get("category"))
            cat_pct = it.get("CategoryPercent", 0)
            buff_str = f" *(+{int(cat_pct)}% Buff)*" if cat_pct > 0 else ""
            lines.append(f"• {c_icon} **{it['Label']}**: **{it['Price']:,}$** / Max {it['Max']:,}${buff_str} ➔ `100%`")
        lines.append("")

    if near_items:
        lines.append(f"⚡ **SÁT ĐỈNH (80% - 99% MAX) ({len(near_items)} món):**")
        for it in near_items[:8]:
            _, c_icon = get_cat_tag_and_icon(it.get("category"))
            trend = "📈" if it.get("Status") == "up" else ("📉" if it.get("Status") == "down" else "➖")
            cat_pct = it.get("CategoryPercent", 0)
            buff_str = f" *(+{int(cat_pct)}% Buff)*" if cat_pct > 0 else ""
            lines.append(f"• {c_icon} **{it['Label']}**: {it['Price']:,}$ / {it['Max']:,}${buff_str} | {trend} — {make_progress_bar(it['Ratio'], 6)}")
        lines.append("")
    elif not max_items:
        top_items = sorted(items, key=lambda x: x.get("Ratio", 0), reverse=True)[:6]
        lines.append("📊 **TOP MẶT HÀNG CAO NHẤT HIỆN TẠI:**")
        for it in top_items:
            _, c_icon = get_cat_tag_and_icon(it.get("category"))
            cat_pct = it.get("CategoryPercent", 0)
            buff_str = f" *(+{int(cat_pct)}% Buff)*" if cat_pct > 0 else ""
            lines.append(f"• {c_icon} **{it['Label']}**: {it['Price']:,}$ / {it['Max']:,}${buff_str} — {make_progress_bar(it['Ratio'], 6)}")
        lines.append("")

    # Biến động gần đây
    latest = getattr(market, "latest_changes", [])
    if latest:
        lines.append("📈 **BIẾN ĐỘNG GIÁ MỚI NHẤT TRONG GAME:**")
        for ch in latest[:4]:
            diff = ch['diff']
            d_str = f"+{diff:,}$" if diff > 0 else f"{diff:,}$"
            icon = "🟢" if diff > 0 else "🔴"
            lines.append(f"{icon} **{ch['Label']}**: {ch['old_price']:,}$ ➔ **{ch['new_price']:,}$** (`{d_str}`)")
        lines.append("")

    lines.append("💡 *Bảng này tự động nhảy số liên tục theo game FiveM. Gõ `!banggia` để xem tất cả.*")
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

_last_dashboard_edit = 0
_last_dashboard_content = ""
_heartbeat_counter = 0

@bot.event
async def on_ready():
    print("=" * 60)
    print(f"[+] Bot đã kết nối thành công: {bot.user} (ID: {bot.user.id})")
    print(f"[+] Phiên bản: v{VERSION}")
    print(f"[+] Số máy chủ đang tham gia: {len(bot.guilds)}")
    cats = market.config.get('enabled_categories', ['all'])
    print(f"[+] Chế độ: THEO DÕI TOÀN BỘ GIÁ THỊ TRƯỜNG (Tất cả mặt hàng từ 80% đến 100% MAX)")
    print(f"[+] Danh mục theo dõi: {cats}")
    print(f"[+] Chu kỳ quét thị trường: {market.config.get('check_interval_seconds', 3)}s (quét liên tục realtime)")
    live_ch = market.config.get("live_channel_id")
    live_msg = market.config.get("live_message_id")
    if live_ch and live_msg:
        print(f"[+] Bảng điện tử Live Market đang ghim tại kênh ID {live_ch} (Message ID: {live_msg})")
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
                await ch.send("🟢 **Bot báo giá đã hoạt động!** (Chế độ: **Toàn bộ mặt hàng thị trường** - Gỗ, Đá, Cá, Nông sản, Nấm, Vật liệu...)")
                print(f"[+] Đã thông báo bot hoạt động tới kênh: #{getattr(ch, 'name', ch_id)}", flush=True)
        except Exception as e:
            print(f"[!] Không thể gửi vào channel: {e}", flush=True)

# Tác vụ chạy ngầm kiểm tra giá định kỳ (Quét liên tục realtime mỗi 3 giây)
@tasks.loop(seconds=market.config.get("check_interval_seconds", 3))
async def auto_price_monitor():
    global _last_dashboard_edit, _last_dashboard_content, _heartbeat_counter
    try:
        now = time.time()
        now_str = datetime.now().strftime("%H:%M:%S")

        # Quét thị trường FiveM realtime
        alerts = market.check_for_alerts()
        changes = getattr(market, "last_detected_changes", [])
        rem = getattr(market, "remaining_seconds", 0)

        # 1. In log console đều đặn để người dùng biết bot đang get dữ liệu liên tục
        if changes:
            ch_strs = [f"{c['Label']} ({c['diff']:+,}$)" for c in changes[:4]]
            print(f"[*] [{now_str}] [{market.active_source}] ⚡ {len(changes)} món biến động: {', '.join(ch_strs)} | Reset sau: {rem}s", flush=True)
        else:
            _heartbeat_counter += 1
            if _heartbeat_counter % 5 == 0:  # Mỗi ~15 giây in 1 log nhịp tim
                max_count = len(market.get_max_items(filter_category=False))
                print(f"[*] [{now_str}] [{market.active_source}] Đang quét realtime... ({len(market.items)} món | Reset sau: {rem}s | {max_count} món MAX)", flush=True)

        # 2. Tự động cập nhật Bảng Điện Tử Live trên Discord (nếu đã kích hoạt qua !live)
        live_ch_id = market.config.get("live_channel_id")
        live_msg_id = market.config.get("live_message_id")
        if live_ch_id and live_msg_id:
            # Cập nhật khi có giá đổi HOẶC mỗi 6-8 giây để cập nhật đồng hồ đếm ngược
            if changes or (now - _last_dashboard_edit >= 6):
                try:
                    target_ch = bot.get_channel(int(live_ch_id)) or await bot.fetch_channel(int(live_ch_id))
                    if target_ch:
                        dash_content = format_live_dashboard(market)
                        if dash_content != _last_dashboard_content:
                            msg_obj = await target_ch.fetch_message(int(live_msg_id))
                            if msg_obj:
                                await msg_obj.edit(content=dash_content)
                                _last_dashboard_content = dash_content
                                _last_dashboard_edit = now
                except Exception:
                    pass

        # 3. Gửi tin nhắn cảnh báo Alert (Món chạm 100% MAX hoặc bị tụt giá)
        if not alerts:
            return

        channel_id = market.config.get("channel_id")
        webhook_url = market.config.get("webhook_url")
        role_id = market.config.get("ping_role_id")

        print(f"[*] [{now_str}] Gửi cảnh báo: {len(alerts)} mặt hàng tới Discord!", flush=True)

        if len(alerts) > 3:
            # Gộp thành 1 danh sách gọn gàng nếu nhiều món cùng lúc
            lines = [f"⚡ **BIẾN ĐỘNG THỊ TRƯỜNG TOÀN BỘ ({len(alerts)} thông báo mới):**"]
            for it in alerts:
                at = it.get("alert_type")
                cat = it.get("category")
                _, cat_icon = get_cat_tag_and_icon(cat)
                diff = it.get("price_diff", 0)
                if at == "PRICE_DROP":
                    lines.append(f"📉 {cat_icon} **{it['Label']}**: Vừa tụt {it.get('prev_price'):,}$ ➔ {it['Price']:,}$ (`{diff:+,}$`) — {make_progress_bar(it['Ratio'], 6)}")
                elif at == "DROP_BELOW_80":
                    lines.append(f"⚠️ {cat_icon} **{it['Label']}**: Tụt dưới 80% (còn {it['Price']:,}$) — {make_progress_bar(it['Ratio'], 6)}")
                elif it["Ratio"] >= 100:
                    lines.append(f"🚨 {cat_icon} **{it['Label']}**: {it['Price']:,}$ / {it['Max']:,}$ — {make_progress_bar(it['Ratio'], 6)}")
                else:
                    lines.append(f"🔥 {cat_icon} **{it['Label']}**: {it['Price']:,}$ / {it['Max']:,}$ — {make_progress_bar(it['Ratio'], 6)}")
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
                at = it.get("alert_type")
                # Chỉ tag role khi chạm MAX 100% (không tag khi tụt giá)
                if role_id and it["Ratio"] >= 100 and at == "MAX":
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
        await ctx.send("⚠️ **Cú pháp:** `!gia <tên vật phẩm>`\n*Ví dụ:* `!gia sắt`, `!gia nấm`, `!gia bột mì`, `!gia cá hồi`, `!gia lúa mì`")
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
    """Xem danh sách các mặt hàng đã chạm max hoặc gần max (toàn bộ thị trường)"""
    items = market.get_all_items()
    cats = market.config.get("enabled_categories")
    await ctx.send(format_max_list(items, enabled_cats=cats))

@bot.command(name="check", aliases=["kiemtra", "scan"])
async def cmd_check(ctx):
    """Quét dữ liệu mới nhất từ FiveM hoặc file và báo các món gần max"""
    market.update()
    items = market.get_all_items()
    cats = market.config.get("enabled_categories")
    await ctx.send("🔄 **Đã cập nhật thị trường!**\n" + format_max_list(items, enabled_cats=cats))

@bot.command(name="kenh", aliases=["setchannel"])
@commands.has_permissions(administrator=True)
async def cmd_setchannel(ctx):
    """Đặt kênh hiện tại làm nơi nhận thông báo giá tự động"""
    ch_id = str(ctx.channel.id)
    market.config["channel_id"] = ch_id
    market.save_config()
    await ctx.send(f"✅ Đã đặt kênh <#{ch_id}> làm kênh nhận **Thông Báo Giá Tự Động**!")

# --- LỆNH BẢNG ĐIỆN TỬ THỊ TRƯỜNG LIVE (REALTIME DASHBOARD) ---
@bot.command(name="live", aliases=["dashboard", "bangdien", "banglive"])
@commands.has_permissions(administrator=True)
async def cmd_live(ctx):
    """Tạo và ghim Bảng Điện Tử Thị Trường Live (tự động cập nhật nhảy giá liên tục)"""
    global _last_dashboard_content, _last_dashboard_edit
    market.update()
    content = format_live_dashboard(market)
    msg = await ctx.send(content)
    market.config["live_channel_id"] = str(ctx.channel.id)
    market.config["live_message_id"] = str(msg.id)
    market.save_config()
    _last_dashboard_content = content
    _last_dashboard_edit = time.time()
    await ctx.send("✅ **Đã kích hoạt Bảng Điện Tử Thị Trường Live!** Bảng trên sẽ tự động cập nhật số liệu và đếm ngược liên tục từng giây như trong game FiveM.")

@bot.command(name="stoplive", aliases=["tatlive"])
@commands.has_permissions(administrator=True)
async def cmd_stoplive(ctx):
    """Tắt chế độ tự động cập nhật Bảng Điện Tử Live"""
    market.config["live_channel_id"] = ""
    market.config["live_message_id"] = ""
    market.save_config()
    await ctx.send("⏹️ **Đã tắt tự động cập nhật Bảng Điện Tử Live.**")

@bot.command(name="timer", aliases=["demnguoc", "time", "reset"])
async def cmd_timer(ctx):
    """Xem thời gian còn lại đến đợt đổi giá tiếp theo của FiveM"""
    market.update()
    rem = getattr(market, "remaining_seconds", 0)
    if rem > 0:
        mins = rem // 60
        secs = rem % 60
        await ctx.send(f"⏱️ **Đếm ngược thị trường FiveM:** Còn **{mins:02d} phút {secs:02d} giây** (`{rem}s`) đến đợt đổi giá tiếp theo!\n🟢 Nguồn: `{market.active_source}`")
    else:
        await ctx.send(f"⏱️ **Thị trường FiveM:** Đang trong chu kỳ tính toán giá mới.\n🟢 Nguồn: `{market.active_source}`")

# --- LỆNH XEM BẢNG GIÁ TOÀN BỘ CÁC MẶT HÀNG ---
@bot.command(name="banggia", aliases=["bangia", "all", "toanbo", "market"])
async def cmd_banggia(ctx):
    """Xem toàn bộ giá tất cả các mặt hàng trên thị trường"""
    market.update()
    items = market.get_all_items()
    chunks = format_all_categories_table(items)
    for c in chunks:
        await ctx.send(c)

@bot.tree.command(name="banggia", description="Xem toàn bộ giá tất cả các mặt hàng trên thị trường")
async def slash_banggia(interaction: discord.Interaction):
    market.update()
    items = market.get_all_items()
    chunks = format_all_categories_table(items)
    await interaction.response.send_message(chunks[0])
    for c in chunks[1:]:
        await interaction.followup.send(c)

# --- LỆNH TỪNG NGHỀ CỤ THỂ ---
@bot.command(name="go", aliases=["wood", "lumberjack"])
async def cmd_go(ctx):
    """Xem toàn bộ giá tất cả các loại Gỗ bán được"""
    market.update()
    items = market.get_all_items()
    chunks = format_category_table("lumberjack", "Nghề Gỗ (Lumberjack)", "🪓", items)
    for c in chunks:
        await ctx.send(c)

@bot.command(name="da", aliases=["quang", "khoangsan", "mining", "stone"])
async def cmd_da(ctx):
    """Xem toàn bộ giá tất cả các loại Đá & Quặng bán được"""
    market.update()
    items = market.get_all_items()
    chunks = format_category_table("mining", "Nghề Đá & Khoáng Sản (Mining)", "⛏️", items)
    for c in chunks:
        await ctx.send(c)

@bot.command(name="ca", aliases=["fish", "fishing", "cauca", "haisan"])
async def cmd_ca(ctx):
    """Xem toàn bộ giá tất cả các loại Cá & Thủy hải sản bán được"""
    market.update()
    items = market.get_all_items()
    chunks = format_category_table("fishing", "Nghề Đánh Bắt Cá & Hải Sản (Fishing)", "🎣", items)
    for c in chunks:
        await ctx.send(c)

@bot.command(name="nongsan", aliases=["farm", "farming", "lua", "rau"])
async def cmd_nongsan(ctx):
    """Xem toàn bộ giá tất cả các loại Nông Sản bán được"""
    market.update()
    items = market.get_all_items()
    chunks = format_category_table("farming", "Nghề Nông Sản & Trồng Trọt (Farming)", "🌾", items)
    for c in chunks:
        await ctx.send(c)

@bot.command(name="nam", aliases=["mushroom", "mushrooms", "hainam"])
async def cmd_nam(ctx):
    """Xem toàn bộ giá tất cả các loại Nấm bán được"""
    market.update()
    items = market.get_all_items()
    chunks = format_category_table("mushrooms", "Nghề Hái Nấm (Mushrooms)", "🍄", items)
    for c in chunks:
        await ctx.send(c)

@bot.command(name="vatlieu", aliases=["materials", "craft", "chetao", "phelieu"])
async def cmd_vatlieu(ctx):
    """Xem toàn bộ giá tất cả các loại Vật Liệu & Chế Tạo"""
    market.update()
    items = market.get_all_items()
    chunks = format_category_table("materials", "Vật Liệu & Chế Tạo (Materials)", "🧱", items)
    for c in chunks:
        await ctx.send(c)

# --- SLASH COMMANDS TỪNG NGHỀ ---
@bot.tree.command(name="go", description="Xem toàn bộ giá tất cả các loại Gỗ bán được")
async def slash_go(interaction: discord.Interaction):
    market.update()
    items = market.get_all_items()
    chunks = format_category_table("lumberjack", "Nghề Gỗ (Lumberjack)", "🪓", items)
    await interaction.response.send_message(chunks[0])
    for c in chunks[1:]:
        await interaction.followup.send(c)

@bot.tree.command(name="da", description="Xem toàn bộ giá tất cả các loại Đá & Quặng bán được")
async def slash_da(interaction: discord.Interaction):
    market.update()
    items = market.get_all_items()
    chunks = format_category_table("mining", "Nghề Đá & Khoáng Sản (Mining)", "⛏️", items)
    await interaction.response.send_message(chunks[0])
    for c in chunks[1:]:
        await interaction.followup.send(c)

@bot.tree.command(name="ca", description="Xem toàn bộ giá tất cả các loại Cá & Thủy hải sản bán được")
async def slash_ca(interaction: discord.Interaction):
    market.update()
    items = market.get_all_items()
    chunks = format_category_table("fishing", "Nghề Đánh Bắt Cá & Hải Sản (Fishing)", "🎣", items)
    await interaction.response.send_message(chunks[0])
    for c in chunks[1:]:
        await interaction.followup.send(c)

@bot.tree.command(name="nongsan", description="Xem toàn bộ giá tất cả các loại Nông Sản bán được")
async def slash_nongsan(interaction: discord.Interaction):
    market.update()
    items = market.get_all_items()
    chunks = format_category_table("farming", "Nghề Nông Sản & Trồng Trọt (Farming)", "🌾", items)
    await interaction.response.send_message(chunks[0])
    for c in chunks[1:]:
        await interaction.followup.send(c)

@bot.tree.command(name="nam", description="Xem toàn bộ giá tất cả các loại Nấm bán được")
async def slash_nam(interaction: discord.Interaction):
    market.update()
    items = market.get_all_items()
    chunks = format_category_table("mushrooms", "Nghề Hái Nấm (Mushrooms)", "🍄", items)
    await interaction.response.send_message(chunks[0])
    for c in chunks[1:]:
        await interaction.followup.send(c)

@bot.tree.command(name="vatlieu", description="Xem toàn bộ giá tất cả các loại Vật Liệu & Chế Tạo")
async def slash_vatlieu(interaction: discord.Interaction):
    market.update()
    items = market.get_all_items()
    chunks = format_category_table("materials", "Vật Liệu & Chế Tạo (Materials)", "🧱", items)
    await interaction.response.send_message(chunks[0])
    for c in chunks[1:]:
        await interaction.followup.send(c)

@bot.command(name="nghe", aliases=["jobs", "chedo", "mode"])
async def cmd_nghe(ctx):
    """Xem trạng thái theo dõi các danh mục mặt hàng"""
    cats = market.config.get("enabled_categories")
    is_all = not cats or "all" in cats
    msg = (
        "📋 **CHẾ ĐỘ THEO DÕI NGHỀ CỦA BOT:**\n"
        f"• 🪓 **Nghề Gỗ (Lumberjack):** {'🟢 ĐANG BẬT' if is_all or 'lumberjack' in cats else '🔴 ĐANG TẮT'}\n"
        f"• ⛏️ **Nghề Đá & Quặng (Mining):** {'🟢 ĐANG BẬT' if is_all or 'mining' in cats else '🔴 ĐANG TẮT'}\n"
        f"• 🎣 **Nghề Câu Cá (Fishing):** {'🟢 ĐANG BẬT' if is_all or 'fishing' in cats else '🔴 ĐANG TẮT'}\n"
        f"• 🌾 **Nghề Nông Sản (Farming):** {'🟢 ĐANG BẬT' if is_all or 'farming' in cats else '🔴 ĐANG TẮT'}\n"
        f"• 🍄 **Nghề Hái Nấm (Mushrooms):** {'🟢 ĐANG BẬT' if is_all or 'mushrooms' in cats or 'mushroom' in cats else '🔴 ĐANG TẮT'}\n"
        f"• 🧱 **Vật Liệu & Chế Tạo (Materials):** {'🟢 ĐANG BẬT' if is_all or 'materials' in cats else '🔴 ĐANG TẮT'}\n\n"
        "✨ *Bot đang ở chế độ **THEO DÕI TOÀN BỘ GIÁ THỊ TRƯỜNG** không giới hạn danh mục!*"
    )
    await ctx.send(msg)

@bot.tree.command(name="nghe", description="Xem các danh mục nghề đang được theo dõi giá")
async def slash_nghe(interaction: discord.Interaction):
    cats = market.config.get("enabled_categories")
    is_all = not cats or "all" in cats
    msg = (
        "📋 **CHẾ ĐỘ THEO DÕI NGHỀ CỦA BOT:**\n"
        f"• 🪓 **Nghề Gỗ (Lumberjack):** {'🟢 ĐANG BẬT' if is_all or 'lumberjack' in cats else '🔴 ĐANG TẮT'}\n"
        f"• ⛏️ **Nghề Đá & Quặng (Mining):** {'🟢 ĐANG BẬT' if is_all or 'mining' in cats else '🔴 ĐANG TẮT'}\n"
        f"• 🎣 **Nghề Câu Cá (Fishing):** {'🟢 ĐANG BẬT' if is_all or 'fishing' in cats else '🔴 ĐANG TẮT'}\n"
        f"• 🌾 **Nghề Nông Sản (Farming):** {'🟢 ĐANG BẬT' if is_all or 'farming' in cats else '🔴 ĐANG TẮT'}\n"
        f"• 🍄 **Nghề Hái Nấm (Mushrooms):** {'🟢 ĐANG BẬT' if is_all or 'mushrooms' in cats or 'mushroom' in cats else '🔴 ĐANG TẮT'}\n"
        f"• 🧱 **Vật Liệu & Chế Tạo (Materials):** {'🟢 ĐANG BẬT' if is_all or 'materials' in cats else '🔴 ĐANG TẮT'}\n\n"
        "✨ *Bot đang ở chế độ **THEO DÕI TOÀN BỘ GIÁ THỊ TRƯỜNG** không giới hạn danh mục!*"
    )
    await interaction.response.send_message(msg)

@bot.command(name="help", aliases=["trogiup", "lenh"])
async def cmd_help(ctx):
    """Xem danh sách hướng dẫn lệnh"""
    help_text = (
        "🤖 **DANH SÁCH LỆNH BOT BÁO GIÁ QUEEN MARKET:**\n"
        "• `!live` (hoặc `/live`): **Bật Bảng Điện Tử Live** — Tin nhắn tự nhảy giá & đếm ngược liên tục như trong game!\n"
        "• `!stoplive`: Tắt tự động cập nhật bảng điện tử live\n"
        "• `!timer` (hoặc `/timer`): Đếm ngược thời gian đến đợt đổi giá tiếp theo của FiveM\n"
        "• `!banggia` (hoặc `/banggia`, `!all`): Xem bảng giá **toàn bộ tất cả mặt hàng** trên thị trường\n"
        "• `!go` (hoặc `/go`): Xem bảng giá toàn bộ mặt hàng Gỗ\n"
        "• `!da` (hoặc `/da`): Xem bảng giá toàn bộ mặt hàng Đá/Quặng/Thỏi kim loại\n"
        "• `!ca` (hoặc `/ca`): Xem bảng giá toàn bộ mặt hàng Cá/Thủy hải sản\n"
        "• `!nongsan` (hoặc `/nongsan`): Xem bảng giá toàn bộ mặt hàng Nông sản\n"
        "• `!nam` (hoặc `/nam`): Xem bảng giá toàn bộ mặt hàng Nấm\n"
        "• `!vatlieu` (hoặc `/vatlieu`): Xem bảng giá toàn bộ mặt hàng Vật liệu/Chế tạo\n"
        "• `!gia <tên>` (hoặc `/gia`): Tra giá 1 món cụ thể (VD: `!gia sắt`, `!gia cá hồi`, `!gia nấm`)\n"
        "• `!max` (hoặc `/max`): Xem tất cả các món đang chạm MAX hoặc từ 80% MAX\n"
        "• `!nghe` (hoặc `/nghe`): Xem trạng thái theo dõi các danh mục\n"
        "• `!check` (hoặc `/kiemtra`): Quét và đồng bộ giá mới nhất ngay lập tức\n"
        "• `!kenh`: *(Admin)* Đặt kênh nhận thông báo giá tự động"
    )
    await ctx.send(help_text)

# ==================== SLASH COMMANDS (/) ====================

@bot.tree.command(name="live", description="Bật Bảng Điện Tử Thị Trường Live (Tự động nhảy giá liên tục như trong game)")
async def slash_live(interaction: discord.Interaction):
    global _last_dashboard_content, _last_dashboard_edit
    market.update()
    content = format_live_dashboard(market)
    await interaction.response.send_message(content)
    msg = await interaction.original_response()
    market.config["live_channel_id"] = str(interaction.channel_id)
    market.config["live_message_id"] = str(msg.id)
    market.save_config()
    _last_dashboard_content = content
    _last_dashboard_edit = time.time()
    await interaction.followup.send("✅ **Đã kích hoạt Bảng Điện Tử Thị Trường Live!** Bảng trên sẽ tự động cập nhật số liệu và đếm ngược liên tục từng giây như trong game FiveM.", ephemeral=True)

@bot.tree.command(name="stoplive", description="Tắt cập nhật Bảng Điện Tử Thị Trường Live")
async def slash_stoplive(interaction: discord.Interaction):
    market.config["live_channel_id"] = ""
    market.config["live_message_id"] = ""
    market.save_config()
    await interaction.response.send_message("⏹️ **Đã tắt tự động cập nhật Bảng Điện Tử Live.**", ephemeral=True)

@bot.tree.command(name="timer", description="Xem thời gian đếm ngược đến đợt đổi giá tiếp theo của FiveM")
async def slash_timer(interaction: discord.Interaction):
    market.update()
    rem = getattr(market, "remaining_seconds", 0)
    if rem > 0:
        mins = rem // 60
        secs = rem % 60
        await interaction.response.send_message(f"⏱️ **Đếm ngược thị trường FiveM:** Còn **{mins:02d} phút {secs:02d} giây** (`{rem}s`) đến đợt đổi giá tiếp theo!\n🟢 Nguồn: `{market.active_source}`")
    else:
        await interaction.response.send_message(f"⏱️ **Thị trường FiveM:** Đang trong chu kỳ tính toán giá mới.\n🟢 Nguồn: `{market.active_source}`")

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

@bot.tree.command(name="max", description="Xem các mặt hàng đã chạm max hoặc gần max (toàn thị trường)")
async def slash_max(interaction: discord.Interaction):
    items = market.get_all_items()
    cats = market.config.get("enabled_categories")
    await interaction.response.send_message(format_max_list(items, enabled_cats=cats))

@bot.tree.command(name="kiemtra", description="Kiểm tra và đồng bộ thị trường ngay lập tức")
async def slash_check(interaction: discord.Interaction):
    market.update()
    items = market.get_all_items()
    cats = market.config.get("enabled_categories")
    await interaction.response.send_message("🔄 **Đã cập nhật thị trường!**\n" + format_max_list(items, enabled_cats=cats))

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
