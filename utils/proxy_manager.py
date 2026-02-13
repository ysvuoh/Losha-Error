import requests
import cloudscraper
import threading
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor

# =========================
# إعدادات
# =========================

PROXY_CHECK_URL = "https://httpbin.org/ip"
PROXY_CHECK_TIMEOUT = 10
PROXY_FILENAME = "proxies.txt"
MAX_WORKERS = 30

# =========================
# متغيرات عامة
# =========================

ACTIVE_PROXIES = []
PROXY_CYCLER = None
ORIGINAL_REQUEST_FUNC = requests.Session.request
FILE_LOCK = threading.Lock()
CYCLER_LOCK = threading.Lock()

# =========================
# تنسيق البروكسي
# =========================

def build_proxy_dict(proxy_line, proxy_type="http"):
    """
    proxy_type = http أو socks5
    """
    parts = proxy_line.strip().split(":")

    if len(parts) == 4:
        ip, port, user, password = parts
        proxy_url = f"{proxy_type}://{user}:{password}@{ip}:{port}"
    elif len(parts) == 2:
        ip, port = parts
        proxy_url = f"{proxy_type}://{ip}:{port}"
    else:
        return None

    return {
        "http": proxy_url,
        "https": proxy_url
    }

# =========================
# فحص البروكسي
# =========================

def check_proxy(proxy_line):
    proxy_ip_port = ":".join(proxy_line.split(":")[:2])

    # نجرب HTTP أولاً
    try:
        proxies = build_proxy_dict(proxy_line, "http")
        r = requests.get(PROXY_CHECK_URL, proxies=proxies, timeout=PROXY_CHECK_TIMEOUT)
        if r.status_code == 200:
            print(f"HTTP WORKING  → {proxy_ip_port}")
            return (proxy_line, "http")
    except:
        pass

    # نجرب SOCKS5
    try:
        proxies = build_proxy_dict(proxy_line, "socks5")
        r = requests.get(PROXY_CHECK_URL, proxies=proxies, timeout=PROXY_CHECK_TIMEOUT)
        if r.status_code == 200:
            print(f"SOCKS5 WORKING → {proxy_ip_port}")
            return (proxy_line, "socks5")
    except:
        pass

    print(f"FAILED → {proxy_ip_port}")
    return None

# =========================
# تحميل وفحص البروكسيات
# =========================

def load_and_clean_proxies():
    global ACTIVE_PROXIES, PROXY_CYCLER

    try:
        with open(PROXY_FILENAME, "r") as f:
            proxies = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("ملف البروكسي غير موجود.")
        return

    if not proxies:
        print("ملف البروكسي فارغ.")
        return

    print(f"بدء فحص {len(proxies)} بروكسي...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(filter(None, executor.map(check_proxy, proxies)))

    ACTIVE_PROXIES = results

    if not ACTIVE_PROXIES:
        print("لم يتم العثور على بروكسي يعمل.")
        return

    PROXY_CYCLER = cycle(ACTIVE_PROXIES)

    # تحديث الملف
    with FILE_LOCK:
        with open(PROXY_FILENAME, "w") as f:
            for proxy_line, _ in ACTIVE_PROXIES:
                f.write(proxy_line + "\n")

    print(f"تم حفظ {len(ACTIVE_PROXIES)} بروكسي يعمل.")

# =========================
# إزالة بروكسي فاشل
# =========================

def remove_proxy(proxy_tuple):
    global ACTIVE_PROXIES, PROXY_CYCLER

    with CYCLER_LOCK:
        if proxy_tuple in ACTIVE_PROXIES:
            ACTIVE_PROXIES.remove(proxy_tuple)

            if ACTIVE_PROXIES:
                PROXY_CYCLER = cycle(ACTIVE_PROXIES)
            else:
                PROXY_CYCLER = None
                print("لا يوجد بروكسي نشط متبقي.")

# =========================
# الحصول على بروكسي
# =========================

def get_next_proxy():
    with CYCLER_LOCK:
        if not PROXY_CYCLER:
            return None
        return next(PROXY_CYCLER)

# =========================
# Monkey Patching
# =========================

def patched_request(self, *args, **kwargs):

    proxy_tuple = get_next_proxy()

    if proxy_tuple and "proxies" not in kwargs:
        proxy_line, proxy_type = proxy_tuple
        kwargs["proxies"] = build_proxy_dict(proxy_line, proxy_type)

    if "timeout" not in kwargs:
        kwargs["timeout"] = 20

    try:
        return ORIGINAL_REQUEST_FUNC(self, *args, **kwargs)

    except requests.exceptions.ProxyError:
        if proxy_tuple:
            print("إزالة بروكسي فاشل أثناء الطلب.")
            remove_proxy(proxy_tuple)

        kwargs.pop("proxies", None)
        return ORIGINAL_REQUEST_FUNC(self, *args, **kwargs)

    except requests.exceptions.RequestException:
        kwargs.pop("proxies", None)
        return ORIGINAL_REQUEST_FUNC(self, *args, **kwargs)

# =========================
# تفعيل النظام
# =========================

def activate_proxy_patching():
    if not ACTIVE_PROXIES:
        print("لا يوجد بروكسيات نشطة.")
        return

    print("تفعيل البروكسي المركزي...")
    requests.Session.request = patched_request
    cloudscraper.Session.request = patched_request
