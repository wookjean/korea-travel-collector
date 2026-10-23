# 수집 1회 실행 (v0): 네이버 키워드 + 정형 API + RSS → run/raw-YYYYMMDD.json
import json, os, re, sys, time, datetime as dt, email.utils, urllib.request, urllib.parse, xml.etree.ElementTree as ET
ENV = dict(os.environ)          # GitHub Actions: Secrets가 환경변수로 들어옴
if os.path.exists(".env"):      # Mac: .env 파일
    for line in open(".env", encoding="utf-8"):
        if "=" in line and not line.startswith("#"):
            k, v = line.rstrip("\n").split("=", 1); ENV[k] = "".join(v.split())
NOW = dt.datetime.now(dt.timezone.utc); TODAY = dt.date.today()
strip = lambda s: re.sub(r"<[^>]+>|&quot;|&amp;|&lt;|&gt;|&apos;|&#39;", "", s or "").strip()
BASE_EX = "분양 아파트 부동산 주가 실적 영업이익 카지노 매출 채용 사망 사고 구속 화재 수사 의원 국회 협찬 체험단 원고료 제공받아 소정의 입찰 공모 공청회 성료 폐막".split()
NH = {"X-NCP-APIGW-API-KEY-ID": ENV["NAVER_CLIENT_ID"], "X-NCP-APIGW-API-KEY": ENV["NAVER_CLIENT_SECRET"]}
def get(url, headers=None, data=None, timeout=25):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", **(headers or {})}, data=data), timeout=timeout)
    return r.read()
# (키워드, 채널, 트랙, 카테고리 힌트, 제목 필수어 정규식, 키워드별 제외어)
KW = [
('"인스파이어 아레나"',"news","빠른","리조트 근거리","인스파이어",""),("파라다이스시티 공연","news","빠른","리조트 근거리","파라다이스",""),
("중국인 관광객","news","빠른","중화권 동향","중국","일본"),("중화권 관광객","news","빠른","중화권 동향","중화권",""),
("내한 공연","news","빠른","① 콘서트·공연","내한",""),("첫 내한","news","빠른","① 콘서트·공연","내한","대전"),
("단독 콘서트 예매","news","빠른","① 콘서트·공연","예매|티켓|콘서트",""),("팬미팅 개최","news","빠른","① 콘서트·공연","팬미팅",""),
("월드투어 서울","news","빠른","① 콘서트·공연","투어",""),("서울 축제 개막","news","빠른","③ 페스티벌","축제","마무리"),
("외국인 교통카드","news","빠른","⑥ 정책·제도","교통카드|티머니",""),("노들섬","news","빠른","② 이벤트·시즌","노들",""),
("한강공원 축제","news","빠른","③ 페스티벌","한강",""),("서울 드론쇼","news","빠른","② 이벤트·시즌","드론","국방 수출 산업"),
("불꽃축제","news","빠른","② 이벤트·시즌","불꽃","여수 성화 도쿄"),("서울 단풍","news","빠른","② 이벤트·시즌","단풍",""),
('"크리스마스 마켓" 서울',"news","빠른","② 이벤트·시즌","크리스마스",""),
("생카 홍대","blog","빠른","① 콘서트·공연","생일카페|생카","후기 작년 종료"),("포토이즘 아티스트","blog","빠른","⑤ 쇼핑·팝업","포토이즘","보정"),
("콘서트 MD 팝업","blog","빠른","⑤ 쇼핑·팝업","MD|굿즈|팝업","재입고 양도 중고"),
("더현대 팝업","blog","느린","⑤ 쇼핑·팝업","팝업",""),("더현대 팝업","news","느린","⑤ 쇼핑·팝업","팝업",""),
("성수 팝업","blog","느린","⑤ 쇼핑·팝업","팝업","기부 수익금 마무리"),("한남 플래그십","blog","느린","⑤ 쇼핑·팝업","한남","벤츠 전시장 매물"),
("성수동 신상","blog","느린","④ 맛집·핫플","성수",""),("웨이팅 성수","blog","느린","④ 맛집·핫플","웨이팅|줄","성수기"),
("성수 핫플","news","느린","④ 맛집·핫플","성수",""),("성수 오픈","news","느린","④ 맛집·핫플","성수|오픈",""),
("영종도 오픈","blog","느린","④ 맛집·핫플","영종","호텔 특가 할인 펜션"),("외국인 여행 앱","news","느린","⑦ 여행 꿀팁","앱",""),
("외국인 짐 배송","news","느린","⑦ 여행 꿀팁","짐",""),("편의점 신상","blog","느린","⑤ 쇼핑·팝업","편의점","알바"),
("서울 야시장","news","느린","② 이벤트·시즌","야시장|마켓",""),("서울 전시 오픈","blog","느린","② 이벤트·시즌","전시","주택전시관 견본주택"),
]
# 모드: daily = 빠른 트랙만, monday = 느린 트랙까지. 인자가 없으면 요일로 정해요.
MODE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("daily", "monday") else ("monday" if TODAY.weekday() == 0 else "daily")
if MODE == "daily": KW = [k for k in KW if k[2] == "빠른"]
raw, runlog = [], []
ONLY = [x for x in os.environ.get("ONLY_BOARDS", "").split(",") if x]   # Mac 보충: 해외에서 막힌 게시판만 읽기
SKIP = [x for x in os.environ.get("SKIP_BOARDS", "").split(",") if x]   # Actions: 해외에서 막힌 게시판 건너뛰기
if ONLY: KW, MODE = [], "보충"
def keep_title(t, must, ex): return re.search(must, t) and not any(x in t for x in BASE_EX + ex.split())
for q, ch, track, cat, must, ex in KW:
    days = 2 if track == "빠른" else 8
    try:
        items = json.loads(get(f"https://naverapihub.apigw.ntruss.com/search/v1/{ch}?" + urllib.parse.urlencode({"query": q, "display": 100, "sort": "date"}), NH))["items"]
    except Exception as e:
        runlog.append(dict(source="N1" if ch == "news" else "N2", key=q, ok=False, err=type(e).__name__)); continue
    n = 0
    for i in items:
        d = email.utils.parsedate_to_datetime(i["pubDate"]) if ch == "news" else dt.datetime.strptime(i["postdate"], "%Y%m%d").replace(tzinfo=dt.timezone.utc)
        t = strip(i["title"])
        if (NOW - d).days < days and keep_title(t, must, ex):
            raw.append(dict(source="N1" if ch == "news" else "N2", channel=ch, keyword=q, track=track, cat_hint=cat, title=t, desc=strip(i["description"])[:160], url=i.get("originallink") or i["link"], date=d.date().isoformat())); n += 1
    runlog.append(dict(source="N1" if ch == "news" else "N2", key=q, ok=True, kept=n)); time.sleep(0.12)
if not ONLY:   # 보충 모드에서는 게시판만 읽어요
    # A1 TourAPI 국문 축제 (법정동 시도: 서울11·부산26·인천28·경기41·제주50), 8주 안 시작
    try:
        p = urllib.parse.urlencode({"serviceKey": ENV["DATA_GO_KR_KEY"], "MobileOS": "ETC", "MobileApp": "TheWeek", "_type": "json", "eventStartDate": TODAY.strftime("%Y%m%d"), "numOfRows": 300, "pageNo": 1})
        its = json.loads(get(f"https://apis.data.go.kr/B551011/KorService2/searchFestival2?{p}"))["response"]["body"]["items"]["item"]
        end = TODAY + dt.timedelta(days=56); n = 0
        for i in its:
            s = i.get("eventstartdate", "")
            if i.get("lDongRegnCd") in ("11", "26", "28", "41", "50") and s and dt.date(int(s[:4]), int(s[4:6]), int(s[6:8])) <= end:
                raw.append(dict(source="A1", channel="api", keyword="축제", track="빠른", cat_hint="③ 페스티벌", title=i["title"], desc=f"{s}~{i.get('eventenddate','')} · {i.get('addr1','')}", url="", date=s)); n += 1
        runlog.append(dict(source="A1", key="searchFestival2", ok=True, kept=n))
    except Exception as e: runlog.append(dict(source="A1", key="searchFestival2", ok=False, err=type(e).__name__))
    # A2 서울 문화행사: 8주 안 시작, 축제·콘서트 + 4-5 무료 필터
    try:
        rows = []
        for a, b in [(1, 1000), (1001, 2000)]:
            rows += json.loads(get(f"http://openapi.seoul.go.kr:8088/{urllib.parse.quote(ENV['SEOUL_OPENAPI_KEY'])}/json/culturalEventInfo/{a}/{b}/"))["culturalEventInfo"]["row"]
        end = TODAY + dt.timedelta(days=56); n = 0
        small = re.compile("정기연주회|합창단|전수발표회|교육|강좌|수업")
        for r in rows:
            try: s = dt.date.fromisoformat(r["STRTDATE"][:10])
            except Exception: continue
            if not (TODAY <= s <= end): continue
            code, free = r["CODENAME"], r["IS_FREE"] == "무료"
            if not (code.startswith("축제") or code in ("콘서트", "국악", "클래식")) or small.search(r["TITLE"]): continue
            if code in ("국악", "클래식") and not free: continue
            raw.append(dict(source="A2", channel="api", keyword=code, track="빠른", cat_hint="② 이벤트·시즌" if code.startswith("축제") else "① 콘서트·공연", title=r["TITLE"], desc=f"{r['DATE']} · {r['PLACE']} · {r['GUNAME']} · {r['ORG_NAME']} · {'무료' if free else '유료'}", url=r.get("HMPG_ADDR") or r.get("ORG_LINK") or "", date=s.isoformat(), free=free)); n += 1
        runlog.append(dict(source="A2", key="culturalEventInfo", ok=True, kept=n))
    except Exception as e: runlog.append(dict(source="A2", key="culturalEventInfo", ok=False, err=type(e).__name__))
    # C1 인스파이어 공연 JSON
    try:
        d = json.loads(get("https://www.inspireresorts.com/api/v1/entertainment/inspire-arena/performances?language=ko"))
        open("run/_inspire_sample.json", "w").write(json.dumps(d, ensure_ascii=False)[:3000])
        def walk(o):
            if isinstance(o, dict):
                if any(k in o for k in ("title", "name")) and any("date" in k.lower() for k in o): yield o
                for v in o.values(): yield from walk(v)
            elif isinstance(o, list):
                for v in o: yield from walk(v)
        n = 0
        for o in walk(d):
            t = strip(str(o.get("title") or o.get("name")))
            dates = " ".join(str(v) for k, v in o.items() if "date" in k.lower())
            raw.append(dict(source="C1", channel="api", keyword="인스파이어 공연", track="빠른", cat_hint="① 콘서트·공연", title=t, desc=dates[:120], url="https://www.inspireresorts.com/ko/entertainment", date=dates[:10])); n += 1
        runlog.append(dict(source="C1", key="performances", ok=True, kept=n))
    except Exception as e: runlog.append(dict(source="C1", key="performances", ok=False, err=type(e).__name__))
    # RSS: D1 연합뉴스 문화, D2 여행신문·트래비, H1 서울시 교통
    BROAD = re.compile("축제|공연|콘서트|팝업|개막|오픈|관광|외국인|전시|페스티벌|개장|행사|교통카드|환승|노선|요금|기후동행|지하철|버스|면세|환급")
    for sid, url, cat, days in [("D1", "https://www.yna.co.kr/rss/culture.xml", "", 2), ("D2", "https://www.traveltimes.co.kr/rss/allArticle.xml", "", 2),
                                 ("D2", "https://www.travie.com/rss/allArticle.xml", "", 2), ("H1", "https://news.seoul.go.kr/traffic/feed", "⑥ 정책·제도", 8)]:
        try:
            root = ET.fromstring(get(url)); n = 0
            for it in root.iter("item"):
                t = strip(it.findtext("title")); pd = it.findtext("pubDate") or ""
                try: d = email.utils.parsedate_to_datetime(pd)
                except Exception: d = NOW
                if d.tzinfo is None: d = d.replace(tzinfo=dt.timezone.utc)
                if (NOW - d).days < days and (cat or BROAD.search(t)) and not any(x in t for x in BASE_EX):
                    raw.append(dict(source=sid, channel="rss", keyword="RSS", track="빠른", cat_hint=cat, title=t, desc=strip(it.findtext("description"))[:160], url=it.findtext("link") or "", date=d.date().isoformat())); n += 1
            runlog.append(dict(source=sid, key=url, ok=True, kept=n))
        except Exception as e: runlog.append(dict(source=sid, key=url, ok=False, err=type(e).__name__))
# 게시판형 수집처 (정책·교통) — run/boards.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boards
CAT = {"C4": "① 콘서트·공연", "C2": "① 콘서트·공연", "C3": "① 콘서트·공연", "C5": "① 콘서트·공연", "A6": "", "A7": "⑥ 정책·제도", "B1": "⑥ 정책·제도", "B2": "⑥ 정책·제도", "H2": "⑥ 정책·제도", "H3": "⑥ 정책·제도", "H4": "⑥ 정책·제도"}
for b in boards.BOARDS:
    if (ONLY and b[1] not in ONLY) or b[1] in SKIP: continue
    try:
        r = boards.read_board(*b)
        for i in r["kept"]:
            raw.append(dict(source=b[0], channel="board", keyword=b[1], track="빠른", cat_hint=CAT.get(b[0], ""), title=i["title"], desc=b[1], url=i["url"], date=i["date"]))
        runlog.append(dict(source=b[0], key=b[1], ok=True, kept=len(r["kept"]), listed=len(r["all"])))
    except Exception as e:
        runlog.append(dict(source=b[0], key=b[1], ok=False, err=str(e)[:80] or type(e).__name__))
    time.sleep(1)
out = f"run/raw-{dt.datetime.now():%Y%m%d-%H%M}.json"
json.dump(dict(run_at=dt.datetime.now().isoformat(timespec="minutes"), mode=MODE, items=raw, log=runlog), open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
from collections import Counter
print(out, "mode", MODE, "items", len(raw)); print(Counter(i["source"] for i in raw))
print([l for l in runlog if not l["ok"]])
