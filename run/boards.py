# 게시판형 수집처 읽기 (정책·교통). 표준 라이브러리만 사용.
import re, ssl, time, html, datetime as dt, http.cookiejar, urllib.request, urllib.parse

UA = "Mozilla/5.0 (compatible; TheWeekCollector/0.1)"
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

# ponytail: 공항철도는 옛 서명 방식 인증서라 그 호스트만 보안 수준을 낮춰 접속해요
_weak = ssl.create_default_context(); _weak.set_ciphers("DEFAULT@SECLEVEL=1")
_weak_opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_weak), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
WEAK_TLS = ("airportrailroad.com",)

def fetch(url, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
    op = _weak_opener if any(h in url for h in WEAK_TLS) else _opener
    for attempt in range(2):   # 연결이 한 번 끊기면 잠깐 쉬고 한 번만 다시 시도
        try:
            raw = op.open(req, timeout=25).read(); break
        except (urllib.error.URLError, ConnectionError) as e:
            if attempt or isinstance(e, urllib.error.HTTPError): raise
            time.sleep(5)
    for enc in ("utf-8", "euc-kr", "cp949"):
        try: return raw.decode(enc)
        except UnicodeDecodeError: pass
    return raw.decode("utf-8", "replace")

DATE = re.compile(r"(20\d{2}|\d{2})[.\-/년]\s?(\d{1,2})[.\-/월]\s?(\d{1,2})")
A = re.compile(r'<a\b([^>]*)>(.*?)</a>', re.S | re.I)
TAG = re.compile(r"<[^>]+>")

def clean(s): return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", s))).strip()
NEW = re.compile(r"^새글\s*|\s*새글작성$|\s*새글$")

def parse_date(s):
    m = DATE.search(s)
    if not m: return None
    y, mo, d = m.groups(); y = int(y) + (2000 if len(y) == 2 else 0)
    try: return dt.date(y, int(mo), int(d))
    except ValueError: return None

def generic(page, base):
    """행(tr/li) 단위로 '의미 있는 링크 1개 + 날짜 1개'를 찾는다."""
    page = re.sub(r"<!--.*?-->", "", page, flags=re.S)   # 주석 속 빈 템플릿(KSPO)이 먼저 걸리지 않게
    out, seen = [], set()
    for block in re.findall(r"<(?:tr|li)\b.*?</(?:tr|li)>", page, re.S | re.I):
        d = parse_date(clean(block))
        if not d: continue
        best = None
        for attrs, inner in A.findall(block):
            tt = re.search(r'title\s*=\s*"([^"]{6,})"', attrs)
            inner_t = clean(inner)
            use_attr = tt and (len(inner_t) < 6 or inner_t.endswith(("...", "…")))   # 목록에서 잘린 제목만 title 속성으로 대신
            t = NEW.sub("", clean(tt.group(1)) if use_attr else inner_t)
            nid = re.search(r'data-id\s*=\s*"(\d+)"', attrs)
            if len(t) < 6: continue
            href = re.search(r'href\s*=\s*["\']([^"\']+)', attrs)
            js = re.search(r"(?:onclick|href)\s*=\s*[\"'][^\"']*?\(([^)]*)\)", attrs)
            url = href.group(1) if href and not href.group(1).startswith(("#", "javascript")) else ""
            if not url and nid and "selectNttList.do" in base:   # 관세청·국세청 같은 정부 CMS 상세 주소
                url = base.replace("selectNttList.do", "selectNttInfo.do") + "&nttSn=" + nid.group(1)
            best = (t, urllib.parse.urljoin(base, html.unescape(url)) if url else base, "")
            break
        if best and best[0] not in seen:
            seen.add(best[0]); out.append(dict(title=best[0], date=d.isoformat(), url=best[1]))
    if out: return out
    # 링크 블록형 (KSPO·SM 뉴스룸·인천공항 웹진형): <a href> 안에 제목(h2·h3·subject·img alt)과 날짜
    for href, body in re.findall(r'<a\s[^>]*?href="([^"#][^"]*)"[^>]*>(.*?)</a>', page, re.S):
        dm = re.search(r'class="date"[^>]*>(.*?)<', body, re.S) or re.search(r'작성일\s*([\d.\-]+)', body)
        tm = re.search(r'<h[2-4][^>]*>(.*?)</h[2-4]>', body, re.S) or re.search(r'class="(?:title|subject)"[^>]*>(.*?)<', body, re.S) or re.search(r'alt="([^"]{6,})"', body)
        if dm and tm and parse_date(dm.group(1)):
            rng = re.findall(r"20\d{2}[.-]\d{1,2}[.-]\d{1,2}", dm.group(1))
            out.append(dict(title=clean(tm.group(1)), date=parse_date(dm.group(1)).isoformat(),
                            end=parse_date(rng[-1]).isoformat() if len(rng) > 1 else None, url=urllib.parse.urljoin(base, html.unescape(href))))
    # 킨텍스: 이미지 alt에 "행사명/시작~종료/"
    for name, a, b in re.findall(r'alt="([^"/]{4,})/(20\d{2}\.\d{2}\.\d{2})~(20\d{2}\.\d{2}\.\d{2})', page):
        out.append(dict(title=clean(name), date=parse_date(a).isoformat(), end=parse_date(b).isoformat(), url=base))
    if out: return out
    # 카드형 목록 (티머니): <a href> 안에 card-tit / card-date
    for href, body in re.findall(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
        t = re.search(r'card-tit[^>]*>(.*?)<', body, re.S); d = re.search(r'card-date[^>]*>(.*?)<', body, re.S)
        if t and d and parse_date(d.group(1)):
            out.append(dict(title=clean(t.group(1)), date=parse_date(d.group(1)).isoformat(), url=urllib.parse.urljoin(base, html.unescape(href))))
    return out

def ticket_opens(page, base):
    """예매처 티켓 오픈 공지 카드 (멜론티켓 tit_consert, YES24 ticket-tit). 날짜 = 티켓 오픈일"""
    out = []
    for href, body in re.findall(r"<a\s[^>]*?href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", page, re.S):
        tm = re.search(r"class=[\"'](?:tit_consert|ticket-tit)[\"'][^>]*>(.*?)</", body, re.S)
        if not tm: continue
        dm = re.search(r"class=[\"'](?:date|ticket-date)[\"'][^>]*>(.*?)</(?:span|p)>", body, re.S)
        d = parse_date(clean(dm.group(1))) if dm else None
        out.append(dict(title=clean(tm.group(1)), date=(d or dt.date.today()).isoformat(), date_known=bool(d), url=urllib.parse.urljoin(base, html.unescape(href))))
    seen, uniq = set(), []
    for i in out:
        if i["title"] not in seen: seen.add(i["title"]); uniq.append(i)
    return uniq

def pcity(url):
    """파라다이스시티 이벤트 목록 JSON (진행 중·오픈 예정)"""
    import json
    d = json.loads(fetch(url, data=b""))
    ymd = lambda s: s.replace(".", "-") if s and s[:4].isdigit() else None
    return [dict(title=r["P_TITLE"] + (" — " + r["P_DESC"] if r.get("P_DESC") else ""), date=ymd(r.get("P_ST_DT")) or dt.date.today().isoformat(),
                 end=ymd(r.get("P_ED_DT")), url="https://www.p-city.com/front/event/eventView?pSeq=%s" % r["P_SEQ"], kind=r.get("P_SRC_CD")) for r in d["rs"]]

# (수집처 ID, 이름, 목록 주소, 제목에 있어야 하는 말 — 빈 문자열이면 전부 통과, [게시판별 제외어])
BOARDS = [
    ("A6", "문체부 보도자료", "https://www.mcst.go.kr/site/s_notice/press/pressList.jsp", "관광|외국인|방한|축제|입국|면세|한류|K-|케이", "포상|인증|공모|시상|임명|인사"),
    ("A6", "관광공사 보도자료", "https://knto.or.kr/pressRelease", "관광|외국인|방한|축제|입국|면세|한류|K-|케이", "포상|인증|공모|기자단|채용|인사"),
    ("A7", "K-ETA 공지", "https://www.k-eta.go.kr/portal/board/viewboardlist.do?tmpltNm=notice", ""),
    ("A7", "하이코리아 공지", "https://www.hikorea.go.kr/board/BoardNtcListR.pt", "입국|비자|사증|외국인|관광|전자여행", "대행기관|채용|입찰"),
    ("A7", "법무부 보도자료", "https://www.moj.go.kr/moj/221/subview.do", "출입국|비자|무비자|입국|사증|전자여행|외국인 관광", "검찰|교정|소송|범죄|수사"),
    ("B1", "인천공항 공지", "https://www.airport.kr/ap_ko/1011/subview.do", ""),
    ("B2", "공항철도 공지", "https://www.airportrailroad.com/help/notice", ""),
    ("H2", "티머니 공지", "https://www.tmoney.co.kr/aeb/cmnctn/notice/readNoticeList.dev", "외국인|관광|교통카드|충전|환불|기후동행|요금"),
    ("H2", "티머니 보도자료", "https://www.tmoney.co.kr/aeb/cmnctn/news/readNewsList.dev", "외국인|관광|교통카드|충전|환불|기후동행|요금"),
    ("H3", "국토부 보도자료", "https://www.molit.go.kr/USR/NEWS/m_71/lst.jsp", "개통|노선|철도|공항|요금|GTX|외국인|항공", "훈련|동정|주택|건설|부동산"),
    ("H3", "SR 공지", "https://etk.srail.kr/main.do", "운행|예매|요금|외국인|SRT|열차"),
    ("H4", "관세청 보도자료", "https://www.customs.go.kr/kcs/na/ntt/selectNttList.do?mi=2891&bbsId=1362", "사후면세|즉시환급|택스리펀|외국인 관광|면세|여행자"),
    ("C2", "KSPO DOME·올림픽공원 공연", "https://www.ksponco.or.kr/olympicpark/eventInfo/eventInfoList?mid=a20301010100", "", "", "schedule"),
    ("C2", "킨텍스 행사", "https://www.kintex.com/web/ko/event/list.do", "콘서트|공연|팬미팅|페스티벌|K-?POP|케이팝|코믹|게임|애니", "", "schedule"),
    ("C3", "SM 뉴스룸", "https://www.smentertainment.com/newsroom/", "콘서트|투어|팬미팅|팝업|공연|페스티벌", ""),
    ("C3", "YG 공지", "https://www.ygfamily.com/ko/news/notice", "SEOUL|서울|INCHEON|인천|KOREA|한국|팬미팅|팝업", ""),
    # 예매처: 공개 오픈 공지 목록만, 하루 1회. NOL 티켓은 자동 접근을 403으로 막아서 넣지 않았어요(키워드 수집이 대신 잡아요)
    ("C4", "멜론티켓 오픈 공지", "https://ticket.melon.com/csoon/index.htm", "", "뮤지컬|연극|아동|가족|클래식", "window"),
    ("C4", "YES24 티켓 오픈 공지", "https://ticket.yes24.com/New/Notice/NoticeMain.aspx", "", "뮤지컬|연극|아동|가족|클래식|\\[부산\\]|\\[대구\\]|\\[광주\\]|\\[대전\\]", "window"),
    ("C5", "파라다이스시티 이벤트", "https://www.p-city.com/front/event/eventListNew", "LIVE|CONCERT|공연|콘서트|페스티벌|FESTIVAL|ART|아트|전시|크리스마스|CHRISTMAS|ODYSSEY|NATURE|쇼|마켓", "WELLNESS|DINING|FEAST|LOUNGE", "schedule"),
    ("H4", "국세청 보도자료", "https://www.nts.go.kr/nts/na/ntt/selectNttList.do?mi=2201&bbsId=1028", "사후면세|즉시환급|택스리펀|외국인 관광|면세"),
]

def read_board(sid, name, url, words, ex="", mode="recent", days=8, save_html=None):
    if url.endswith("eventListNew"):
        items, page = pcity(url), ""
    else:
        page = fetch(url)
        if len(page) < 3000 and "점검" in page:
            raise RuntimeError("사이트 점검 중")   # 인천공항처럼 정기 점검 시간에는 안내 화면만 와요
        if save_html: open(save_html, "w", encoding="utf-8").write(page)
        items = ticket_opens(page, url) if mode == "window" else generic(page, url)
    items.sort(key=lambda x: x["date"], reverse=True)   # 고정글이 섞여도 날짜순
    today = dt.date.today()
    if mode == "schedule":   # 공연장·행사 일정: 8주 안에 시작하거나 지금 진행 중인 것
        lim = (today + dt.timedelta(days=56)).isoformat(); t0 = today.isoformat()
        recent = [i for i in items if (t0 <= i["date"] <= lim) or (i["date"] < t0 and (i.get("end") or "") >= t0)]
    elif mode == "window":   # 티켓 오픈: 최근 8일 ~ 앞으로 8주 사이에 오픈하는 것
        lo, hi = (today - dt.timedelta(days=days)).isoformat(), (today + dt.timedelta(days=56)).isoformat()
        recent = [i for i in items if lo <= i["date"] <= hi]
    else:
        cut = (today - dt.timedelta(days=days)).isoformat()
        recent = [i for i in items if i["date"] >= cut]
    kept = [i for i in recent if not words or re.search(words, i["title"])]
    if ex: kept = [i for i in kept if not re.search(ex, i["title"])]
    return dict(source=sid, name=name, url=url, all=items, recent=recent, kept=kept)

if __name__ == "__main__":
    for n, b in enumerate(BOARDS):
        try:
            r = read_board(*b, save_html=f"run/html/{n:02d}.html")
            print(f"\n## {b[0]} {b[1]} — 목록 {len(r['all'])}건 · 8일 내 {len(r['recent'])} · 거른 뒤 {len(r['kept'])}")
            for i in r["all"][:5]: print("  -", i["date"], i["title"][:60], "|", i["url"])
        except Exception as e:
            print(f"\n## {b[0]} {b[1]} — 실패: {type(e).__name__}: {str(e)[:80]}")
        time.sleep(1)
