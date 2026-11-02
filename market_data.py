import json
import os
import sys
import time
import unicodedata
import urllib.request

def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def strip_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để tìm kiếm không dấu tiện lợi (ví dụ: 'sat' -> tìm 'Thỏi Sắt')"""
    if not text:
        return ""
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text.replace('đ', 'd').replace('Đ', 'D').lower().strip()

CATEGORY_NAMES = {
    "mining": "⛏️ Khai Thác Khoáng Sản",
    "fishing": "🎣 Đánh Bắt Thủy Hải Sản",
    "farming": "🌾 Trồng Trọt & Nông Sản",
    "mushroom": "🍄 Thu Hoạch Nấm",
    "hunting": "🏹 Săn Bắn Động Vật",
    "lumberjack": "🪓 Đốn Gỗ & Lâm Nghiệp",
    "crafting": "🛠️ Chế Biến & Gia Công",
    "other": "📦 Mặt Hàng Khác"
}

import base64

_ENC_TOKEN = b"TVRVMk5UZ3hNamN4TURjek5qYzVNelkyTUEuR25EOUJILjRGd0lqQ2RDYVNrcFpXVDVtcDFEd2diNUd0NDZwRHFfWm5IUDU4"
DEFAULT_BOT_TOKEN = base64.b64decode(_ENC_TOKEN).decode()

DEFAULT_CONFIG = {
    "application_id": "1565812710736793660",
    "client_secret": "EgfBnIVsps2qU5xw1WoOy-p0xD9ZdCWe",
    "bot_token": DEFAULT_BOT_TOKEN,
    "webhook_url": "",
    "channel_id": "1566693963522642050",
    "alert_threshold_percent": 80,
    "check_interval_seconds": 30,
    "auto_scan_cdp": True,
    "cdp_port": 13172,
    "market_file_path": "market_prices.json",
    "ping_role_id": ""
}

class MarketManager:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config = self.load_config()
        self.market_file = self.config.get("market_file_path", "market_prices.json")
        self.cdp_port = self.config.get("cdp_port", 13172)
        self.auto_scan_cdp = self.config.get("auto_scan_cdp", True)
        self.threshold = float(self.config.get("alert_threshold_percent", 80))

        self.items = []
        self.raw_data = None
        self.last_file_mtime = 0
        self.last_alert_states = {}  # {item_name: {"price": int, "state": "MAX"|"NEAR_MAX", "time": float}}

        # Nạp dữ liệu ban đầu
        self.load_from_file()

    def load_config(self):
        cfg = dict(DEFAULT_CONFIG)
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                    if isinstance(user_cfg, dict):
                        # Gộp cấu hình của user (ưu tiên những trường không rỗng)
                        for k, v in user_cfg.items():
                            if v is not None and v != "":
                                cfg[k] = v
            except Exception as e:
                print(f"[!] Lỗi đọc config: {e}")
        else:
            # Nếu chưa có file config.json, tự động tạo mới có sẵn token cho người khác dùng ngay
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
                print(f"[+] Đã tự tạo file cấu hình sẵn: {self.config_path}")
            except Exception:
                pass
        return cfg

    def save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[!] Lỗi lưu config: {e}")

    def load_from_file(self):
        """Đọc danh sách giá từ file market_prices.json"""
        import shutil
        base_dir = get_base_dir()
        paths_to_check = [
            os.path.join(base_dir, self.market_file) if not os.path.isabs(self.market_file) else self.market_file,
            os.path.join(base_dir, "market_prices.json"),
            r"E:\codeminigame\market_prices.json"
        ]
        
        target_path = None
        for p in paths_to_check:
            if p and os.path.exists(p):
                target_path = p
                break

        # Nếu máy khác chưa có file market_prices.json, lấy từ file bundle bên trong exe
        if not target_path:
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                bundled = os.path.join(meipass, "market_prices.json")
                if os.path.exists(bundled):
                    try:
                        dest = os.path.join(base_dir, "market_prices.json")
                        shutil.copy2(bundled, dest)
                        target_path = dest
                    except Exception:
                        target_path = bundled

        if not target_path:
            return False

        try:
            mtime = os.path.getmtime(target_path)
            if mtime == self.last_file_mtime and self.items:
                return False  # File không thay đổi

            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                self.raw_data = data
                raw_items = data.get("items", [])
            elif isinstance(data, list):
                raw_items = data
            else:
                raw_items = []

            if raw_items:
                self.items = self._process_items(raw_items)
                self.last_file_mtime = mtime
                return True
        except Exception as e:
            print(f"[!] Lỗi đọc file giá thị trường ({target_path}): {e}")
        return False

    def _process_items(self, raw_items):
        processed = []
        for it in raw_items:
            price = int(it.get("Price", 0))
            max_price = int(it.get("Max", 0))
            min_price = int(it.get("Min", 0))
            base_price = int(it.get("BasePrice", 0))
            ratio = (price / max_price * 100) if max_price > 0 else 0

            # Phân loại trạng thái
            if max_price > 0 and price >= max_price:
                level = "MAX"
                level_desc = "🚨 CHẠM ĐỈNH MAX (100%)"
                color = 0x2ECC71  # Xanh lục / Hoặc Đỏ nổi bật
            elif ratio >= self.threshold:
                level = "NEAR_MAX"
                level_desc = f"🔥 SÁT ĐỈNH ({ratio:.1f}%)"
                color = 0xF1C40F  # Vàng cam
            elif price > base_price:
                level = "GOOD"
                level_desc = f"📈 Giá Ổn ({ratio:.1f}%)"
                color = 0x3498DB  # Xanh dương
            else:
                level = "NORMAL"
                level_desc = f"📉 Giá Thấp ({ratio:.1f}%)"
                color = 0x95A5A6  # Xám

            processed.append({
                "itemName": it.get("itemName", ""),
                "Label": it.get("Label", it.get("itemName", "Chưa rõ")),
                "Price": price,
                "Min": min_price,
                "BasePrice": base_price,
                "Max": max_price,
                "Ratio": ratio,
                "Status": it.get("Status", "equal"),
                "category": it.get("category", "other"),
                "level": level,
                "level_desc": level_desc,
                "color": color,
                "image": it.get("image", "")
            })
        return processed

    def fetch_from_fivem_cdp(self):
        """Kết nối FiveM qua port CEF 13172 để lấy dữ liệu thời gian thực trong RAM"""
        if not self.auto_scan_cdp:
            return False

        try:
            url = f"http://127.0.0.1:{self.cdp_port}/json"
            req = urllib.request.urlopen(url, timeout=1.5)
            targets = json.loads(req.read().decode("utf-8"))
            
            root_target = None
            for t in targets:
                if "root.html" in t.get("url", ""):
                    root_target = t
                    break
            
            if not root_target:
                return False

            import websocket
            ws = websocket.WebSocket()
            ws.connect(root_target["webSocketDebuggerUrl"], timeout=2.5)

            # Đọc trực tiếp từ React Fiber Store của queen_market trong RAM
            js_query = """(() => {
                const qm = window.frames['queen_market'];
                if (!qm) return null;
                const rootEl = qm.document.getElementById('root');
                if (!rootEl) return null;
                const rKey = Object.keys(rootEl).find(k => k.startsWith('__reactContainer') || k.startsWith('__reactFiber'));
                if (!rKey) return null;
                let fiber = rootEl[rKey];

                let queue = [fiber];
                let visited = 0;
                while (queue.length > 0 && visited < 1500) {
                    let node = queue.shift();
                    visited++;
                    if (!node) continue;

                    let ms = node.memoizedState;
                    while (ms) {
                        let st = ms.memoizedState;
                        if (st && typeof st === 'object' && !Array.isArray(st)) {
                            if ((st.potato && st.potato.Price !== undefined) || (st.ls_gold_ingot && st.ls_gold_ingot.Price !== undefined)) {
                                return Object.values(st);
                            }
                        }
                        ms = ms.next;
                    }
                    if (node.child) queue.push(node.child);
                    if (node.sibling) queue.push(node.sibling);
                }
                return null;
            })()"""

            ws.send(json.dumps({
                "id": 888,
                "method": "Runtime.evaluate",
                "params": {"expression": js_query, "returnByValue": True}
            }))
            
            resp = json.loads(ws.recv())
            ws.close()

            market_data = resp.get("result", {}).get("result", {}).get("value")
            if market_data:
                raw_items = market_data if isinstance(market_data, list) else market_data.get("items", [])
                if raw_items:
                    self.items = self._process_items(raw_items)
                    # Lưu đè vào file local
                    save_path = os.path.join(get_base_dir(), "market_prices.json")
                    with open(save_path, "w", encoding="utf-8") as f:
                        json.dump(raw_items, f, indent=2, ensure_ascii=False)
                    # Đồng bộ sang codeminigame nếu có
                    try:
                        with open(r"E:\codeminigame\market_prices.json", "w", encoding="utf-8") as f:
                            json.dump(raw_items, f, indent=2, ensure_ascii=False)
                    except Exception:
                        pass
                    return True
        except Exception:
            pass
        return False

    def update(self):
        """Cập nhật giá từ FiveM (nếu đang bật game) hoặc từ file json"""
        updated_cdp = self.fetch_from_fivem_cdp()
        if not updated_cdp:
            self.load_from_file()

    def get_all_items(self):
        self.update()
        return self.items

    def search_items(self, query: str):
        """Tìm kiếm vật phẩm theo tên (hỗ trợ cả gõ không dấu, viết hoa thường, mã item)"""
        self.update()
        if not query:
            return self.items

        q_clean = strip_accents(query)
        exact_matches = []
        partial_matches = []

        for it in self.items:
            name_clean = strip_accents(it["Label"])
            code_clean = strip_accents(it["itemName"])

            if q_clean == name_clean or q_clean == code_clean:
                exact_matches.append(it)
            elif q_clean in name_clean or q_clean in code_clean:
                partial_matches.append(it)

        return exact_matches if exact_matches else partial_matches

    def get_near_max_items(self, threshold=None):
        """Lấy danh sách các món đang sát max (>= threshold) hoặc chạm max"""
        self.update()
        thresh = threshold if threshold is not None else self.threshold
        matched = [it for it in self.items if it["Ratio"] >= thresh]
        matched.sort(key=lambda x: x["Ratio"], reverse=True)
        return matched

    def get_max_items(self):
        """Lấy danh sách các món đạt 100% max giá"""
        self.update()
        matched = [it for it in self.items if it["Max"] > 0 and it["Price"] >= it["Max"]]
        matched.sort(key=lambda x: x["Price"], reverse=True)
        return matched

    def get_items_by_category(self, cat_key):
        self.update()
        return [it for it in self.items if it.get("category") == cat_key]

    def check_for_alerts(self):
        """
        Kiểm tra và thông báo khi vật phẩm đạt từ 80% đến 100% MAX.
        Chống spam:
        - Chỉ gửi khi mới chạm mốc >= 80% hoặc chạm đỉnh 100% MAX hoặc giá tăng cao hơn.
        - Nhắc lại sau 2 tiếng nếu vẫn giữ giá cao.
        """
        self.update()
        alerts = []
        now = time.time()
        thresh = float(self.config.get("alert_threshold_percent", 80))

        for it in self.items:
            item_name = it["itemName"]
            price = it["Price"]
            max_price = it["Max"]
            ratio = it["Ratio"]

            is_eligible = (max_price > 0 and ratio >= thresh)

            if not is_eligible:
                if item_name in self.last_alert_states:
                    del self.last_alert_states[item_name]
                continue

            prev = self.last_alert_states.get(item_name)
            should_alert = False

            if not prev:
                should_alert = True
            else:
                # Nếu từ sát max (<100%) nhảy lên chạm max (>=100%)
                if prev.get("ratio", 0) < 100 and ratio >= 100:
                    should_alert = True
                # Hoặc giá tiếp tục tăng cao hơn đỉnh cũ
                elif price > prev.get("price", 0):
                    should_alert = True
                # Hoặc giữ giá cao liên tục sau 2 tiếng thì nhắc lại
                elif (now - prev.get("time", 0)) > 7200:
                    should_alert = True

            if should_alert:
                self.last_alert_states[item_name] = {
                    "price": price,
                    "ratio": ratio,
                    "time": now
                }
                alerts.append(it)

        alerts.sort(key=lambda x: x["Ratio"], reverse=True)
        return alerts
