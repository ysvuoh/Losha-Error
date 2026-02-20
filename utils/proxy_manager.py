import requests
import cloudscraper
import threading
import time
import os
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor
from urllib3.util.retry import Retry

# Try to import logger, fallback to print if not available
try:
    from utils.logger import bot_logger as logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("ProxyHandler")

# =========================
# SETTINGS
# =========================

PROXY_CHECK_URL = "https://httpbin.org/ip"
PROXY_CHECK_TIMEOUT = 2  # Reduced timeout for faster checking
MAX_LATENCY_THRESHOLD = 1.5  # Only very fast proxies
PROXY_FILENAME = "proxies.txt"
MAX_WORKERS = 50 
CHECK_INTERVAL = 300  # 5 minutes

# =========================
# GLOBALS
# =========================

ACTIVE_PROXIES = [] 
PROXY_CYCLER = None
ORIGINAL_REQUEST_FUNC = requests.Session.request
CYCLER_LOCK = threading.Lock()

# PERFORMANCE FIX: Advanced Connection Pooling
retries = Retry(total=0, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
adapter = requests.adapters.HTTPAdapter(
    pool_connections=500, 
    pool_maxsize=500, 
    max_retries=retries,
    pool_block=False
)

# =========================
# PROXY FORMATTING
# =========================

def build_proxy_dict(proxy_line, proxy_type="http"):
    line = proxy_line.strip()
    if not line: return None
    try:
        if "@" in line:
            auth, addr = line.split("@")
            proxy_url = f"{proxy_type}://{auth}@{addr}"
        else:
            parts = line.split(":")
            if len(parts) == 4:
                ip, port, user, password = parts
                proxy_url = f"{proxy_type}://{user}:{password}@{ip}:{port}"
            elif len(parts) == 2:
                ip, port = parts
                proxy_url = f"{proxy_type}://{ip}:{port}"
            else:
                return None
        return {"http": proxy_url, "https": proxy_url}
    except Exception:
        return None

# =========================
# PROXY CHECKING
# =========================

def check_proxy(proxy_line):
    for ptype in ["http", "socks5"]:
        try:
            proxies = build_proxy_dict(proxy_line, ptype)
            if not proxies: continue
            
            start_time = time.time()
            with requests.Session() as s:
                r = s.get(PROXY_CHECK_URL, proxies=proxies, timeout=PROXY_CHECK_TIMEOUT)
                latency = time.time() - start_time
                
                if r.status_code == 200:
                    is_fast = latency <= MAX_LATENCY_THRESHOLD
                    return (proxy_line, ptype, latency, is_fast)
        except:
            continue
    return None

# =========================
# BACKGROUND VALIDATOR
# =========================

def perform_proxy_check():
    global ACTIVE_PROXIES, PROXY_CYCLER
    
    try:
        if not os.path.exists(PROXY_FILENAME):
            logger.warning(f"Proxy file {PROXY_FILENAME} not found. Bot will continue without proxies.")
            with CYCLER_LOCK:
                ACTIVE_PROXIES = []
                PROXY_CYCLER = None
            return
            
        with open(PROXY_FILENAME, "r") as f:
            proxies = list(set([line.strip() for line in f if line.strip()]))
    except Exception as e:
        logger.error(f"Failed to read proxy file: {e}")
        return

    if not proxies:
        logger.warning("Proxy file is empty. Bot will continue without proxies.")
        with CYCLER_LOCK:
            ACTIVE_PROXIES = []
            PROXY_CYCLER = None
        return

    logger.info(f"Refreshing {len(proxies)} proxies... (Anti-slowdown mode)")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(filter(None, executor.map(check_proxy, proxies)))

    results.sort(key=lambda x: (not x[3], x[2]))

    with CYCLER_LOCK:
        ACTIVE_PROXIES = results
        if ACTIVE_PROXIES:
            PROXY_CYCLER = cycle(ACTIVE_PROXIES)
            fast_count = sum(1 for p in ACTIVE_PROXIES if p[3])
            logger.info(f"Active: {len(ACTIVE_PROXIES)} | Fast: {fast_count}. Speed optimization applied.")
        else:
            PROXY_CYCLER = None
            logger.error("No working proxies found. Bot will continue without proxies.")

def proxy_validator_loop():
    while True:
        try:
            perform_proxy_check()
        except Exception as e:
            logger.error(f"Error in proxy validator loop: {e}")
        time.sleep(CHECK_INTERVAL)

def load_and_clean_proxies():
    threading.Thread(target=proxy_validator_loop, daemon=True).start()

# =========================
# GET NEXT PROXY
# =========================

def get_next_proxy():
    with CYCLER_LOCK:
        if not PROXY_CYCLER or not ACTIVE_PROXIES:
            return None
        try:
            return next(PROXY_CYCLER)
        except (StopIteration, TypeError):
            return None

# =========================
# MONKEY PATCHING
# =========================

def patched_request(self, method, url, *args, **kwargs):
    # Apply high-performance adapter to all sessions
    if not hasattr(self, '_pool_optimized'):
        self.mount('http://', adapter)
        self.mount('https://', adapter)
        self._pool_optimized = True

    # CRITICAL: DO NOT USE PROXY FOR TELEGRAM API OR IF EXPLICITLY DISABLED
    is_telegram = "api.telegram.org" in url
    use_proxy = kwargs.pop("use_proxy", True)
    
    proxy_tuple = None
    if not is_telegram and use_proxy:
        proxy_tuple = get_next_proxy()

    if proxy_tuple and "proxies" not in kwargs:
        proxy_line, proxy_type, _, _ = proxy_tuple
        kwargs["proxies"] = build_proxy_dict(proxy_line, proxy_type)

    # PERFORMANCE FIX: Timeout removed for maximum stability
    if "timeout" not in kwargs:
        kwargs["timeout"] = None

    try:
        return ORIGINAL_REQUEST_FUNC(self, method, url, *args, **kwargs)
    except Exception:
        # If it's telegram, just retry once without any modification
        if is_telegram:
            try:
                return ORIGINAL_REQUEST_FUNC(self, method, url, *args, **kwargs)
            except:
                raise

        # For other requests, if proxy failed, try WITHOUT proxy immediately
        if "proxies" in kwargs:
            kwargs.pop("proxies", None)
            kwargs["timeout"] = 15 # Increased timeout for direct fallback
            try:
                return ORIGINAL_REQUEST_FUNC(self, method, url, *args, **kwargs)
            except:
                pass
        
        return ORIGINAL_REQUEST_FUNC(self, method, url, *args, **kwargs)

def activate_proxy_patching():
    requests.Session.request = patched_request
    if 'cloudscraper' in globals():
        cloudscraper.Session.request = patched_request
    logger.info("Proxy patching active. Auto-fallback to Direct Connection enabled.")
