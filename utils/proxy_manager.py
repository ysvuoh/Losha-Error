import requests
import cloudscraper
import threading
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor

# --- إعدادات ---
PROXY_CHECK_URL = "http://httpbin.org/ip"  # موقع خفيف وموثوق للتحقق من البروكسي
PROXY_CHECK_TIMEOUT = 10  # مهلة التحقق من البروكسي بالثواني
PROXY_FILENAME = "proxies.txt" # اسم ملف البروكسيات

# --- متغيرات عامة ---
ACTIVE_PROXIES = []  # قائمة البروكسيات التي تعمل فقط (بالتنسيق الأصلي)
PROXY_CYCLER = None
ORIGINAL_REQUEST_FUNC = requests.Session.request
FILE_LOCK = threading.Lock() # قفل لمنع التعارض عند الكتابة في الملف

def format_proxy_url(proxy_line):
    """
    تحول البروكسي من تنسيق ip:port:user:pass أو ip:port إلى http://user:pass@ip:port
    """
    parts = proxy_line.strip().split(':')
    if len(parts) == 4:
        # تنسيق: ip:port:user:pass
        ip, port, user, password = parts
        return f"http://{user}:{password}@{ip}:{port}"
    elif len(parts) == 2:
        # تنسيق بسيط: ip:port
        ip, port = parts
        return f"http://{ip}:{port}"
    else:
        # إذا كان التنسيق بالفعل URL، قم بإرجاعه كما هو
        return proxy_line

def check_proxy(proxy_line):
    """
    يفحص بروكسي واحد. يرجع البروكسي الأصلي (سطر الملف) إذا كان يعمل، و None إذا فشل.
    """
    proxy_url = format_proxy_url(proxy_line) # تحويل التنسيق قبل الفحص
    try:
        proxies = {"http": proxy_url, "https": proxy_url}
        response = requests.get(PROXY_CHECK_URL, proxies=proxies, timeout=PROXY_CHECK_TIMEOUT)
        if response.status_code == 200:
            return proxy_line # إرجاع السطر الأصلي من الملف
    except (requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.RequestException) as e:
        # طباعة رسالة خطأ واضحة للمساعدة في التشخيص
        proxy_ip_port = ":".join(proxy_line.split(':')[:2])
        print(f"❌ فشل فحص البروكسي: {proxy_ip_port} | السبب: {type(e).__name__}")
    return None

def load_and_clean_proxies():
    """
    الوظيفة الرئيسية: تقرأ البروكسيات، تفحصها بالتوازي، وتحدث الملف والقائمة النشطة.
    """
    global ACTIVE_PROXIES, PROXY_CYCLER
    
    initial_proxies = []
    try:
        with open(PROXY_FILENAME, "r") as f:
            initial_proxies = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"ℹ️ ملف البروكسيات '{PROXY_FILENAME}' غير موجود. لن يتم استخدام بروكسيات.")
        return

    if not initial_proxies:
        print("ℹ️ ملف البروكسيات فارغ. لن يتم استخدام بروكسيات.")
        return

    print(f"🔍 بدء فحص {len(initial_proxies)} بروكسي...")
    
    with ThreadPoolExecutor(max_workers=20) as executor: # زيادة عدد العمال لتسريع الفحص
        working_proxies = list(filter(None, executor.map(check_proxy, initial_proxies)))

    ACTIVE_PROXIES = working_proxies
    
    if not ACTIVE_PROXIES:
        print("❌ لم يتم العثور على أي بروكسي يعمل.")
    else:
        print(f"✅ تم العثور على {len(ACTIVE_PROXIES)} بروكسي يعمل وجاهز للاستخدام.")
        PROXY_CYCLER = cycle(ACTIVE_PROXIES)

    with FILE_LOCK:
        try:
            with open(PROXY_FILENAME, "w") as f:
                if ACTIVE_PROXIES:
                    f.write("\n".join(ACTIVE_PROXIES) + "\n")
            print(f"🔄 تم تحديث ملف '{PROXY_FILENAME}' ليحتوي على البروكسيات العاملة فقط.")
        except IOError as e:
            print(f"🔥 خطأ حاد: لم نتمكن من الكتابة في ملف البروكسيات: {e}")

def remove_proxy_from_active_list(proxy_line):
    """
    يزيل البروكسي من القائمة النشطة ومن أداة التدوير أثناء تشغيل البوت.
    """
    global ACTIVE_PROXIES, PROXY_CYCLER
    if proxy_line in ACTIVE_PROXIES:
        proxy_ip_port = ":".join(proxy_line.split(':')[:2])
        print(f"🔻 إزالة البروكسي الفاشل من القائمة النشطة: {proxy_ip_port}")
        ACTIVE_PROXIES.remove(proxy_line)
        if ACTIVE_PROXIES:
            PROXY_CYCLER = cycle(ACTIVE_PROXIES)
        else:
            PROXY_CYCLER = None
            print("⚠️ تحذير: لم يتبق أي بروكسي نشط.")

def get_next_proxy_dict():
    """
    الحصول على البروكسي التالي من القائمة النشطة وتنسيقه كـ URL.
    """
    if not PROXY_CYCLER:
        return None
    
    try:
        proxy_line = next(PROXY_CYCLER)
        proxy_url = format_proxy_url(proxy_line)
        return {"http": proxy_url, "https": proxy_url, "line": proxy_line}
    except StopIteration:
        return None

def patched_request(self, *args, **kwargs):
    """
    الدالة المعدلة التي تضيف البروكسي وتتعامل مع الأخطاء.
    """
    proxy_info = get_next_proxy_dict()
    
    if proxy_info and 'proxies' not in kwargs:
        kwargs['proxies'] = {"http": proxy_info["http"], "https": proxy_info["https"]}
    
    if 'timeout' not in kwargs:
        kwargs['timeout'] = 20

    try:
        return ORIGINAL_REQUEST_FUNC(self, *args, **kwargs)
    except requests.exceptions.ProxyError as e:
        if proxy_info:
            remove_proxy_from_active_list(proxy_info["line"])
        
        print(f"🔁 فشل البروكسي أثناء الطلب. إعادة المحاولة بدون بروكسي...")
        kwargs.pop('proxies', None)
        return ORIGINAL_REQUEST_FUNC(self, *args, **kwargs)
    except requests.exceptions.RequestException as e:
        # التعامل مع أخطاء الشبكة الأخرى
        print(f"🌐 خطأ في الشبكة: {type(e).__name__}. إعادة المحاولة بدون بروكسي...")
        kwargs.pop('proxies', None)
        return ORIGINAL_REQUEST_FUNC(self, *args, **kwargs)


def activate_proxy_patching():
    """
    الدالة الرئيسية التي تقوم بتفعيل الـ Monkey Patching.
    """
    if not ACTIVE_PROXIES:
        print("ℹ️ لم يتم تفعيل البروكسيات لعدم وجود بروكسيات عاملة.")
        return

    print("🚀 تفعيل البروكسي المركزي لجميع طلبات 'requests' و 'cloudscraper'...")
    requests.Session.request = patched_request
    cloudscraper.Session.request = patched_request
