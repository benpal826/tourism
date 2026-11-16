import pytest

from carbon.sources.assembly import AssemblyBillsSource
from carbon.sources.eu import EuPresscornerSource
from carbon.sources.registry import build_sources

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>Commission proposes new climate target for 2040</title><link>https://ec.europa.eu/1</link>
<pubDate>Mon, 02 Nov 2026 09:00:00 GMT</pubDate><description>Greenhouse gas emissions</description></item>
<item><title>Commission approves state aid for assets in rail</title><link>https://ec.europa.eu/2</link>
<pubDate>Mon, 02 Nov 2026 10:00:00 GMT</pubDate><description>Railway</description></item>
</channel></rss>""".encode()


class RssResp:
    content = RSS


class OneClient:
    def __init__(self, resp):
        self.resp = resp

    def get(self, url, **kw):
        return self.resp


def test_eu_keeps_only_climate_items_and_uses_word_boundaries():
    arts = EuPresscornerSource(client=OneClient(RssResp())).fetch()
    assert [a.url for a in arts] == ["https://ec.europa.eu/1"]      # 'assets' 안의 'ets' 에 걸리지 않음
    a = arts[0]
    assert a.source_type == "official" and a.agency == "European Commission" and a.lang == "en"


def test_eu_unreachable_is_failure():
    src = EuPresscornerSource(client=OneClient(None))
    assert src.fetch() == [] and src.failures == ["EU presscorner"]


# 국회 API ----------------------------------------------------------------------------------
BILLS = {"nzmimeepazxkubdpn": [
    {"head": [{"list_total_count": 2}, {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다."}}]},
    {"row": [
        {"BILL_NAME": "기후위기 대응을 위한 탄소중립ㆍ녹색성장 기본법 일부개정법률안", "PROPOSE_DT": "2026-10-20",
         "PROPOSER": "박지혜의원 등 10인", "COMMITTEE": "환경노동위원회", "PROC_RESULT": None,
         "DETAIL_LINK": "http://likms.assembly.go.kr/bill/billDetail.do?billId=PRC_A&ageFrom=22&ageTo=22"},
        {"BILL_NAME": "", "DETAIL_LINK": "http://x"},
    ]}]}
NO_DATA = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}


class JsonResp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class ApiSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.params = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.params.append(params)
        return JsonResp(self.responses.pop(0) if self.responses else BILLS)


def test_assembly_parse_handles_rows_and_no_data():
    assert len(AssemblyBillsSource.parse(BILLS)) == 2
    assert AssemblyBillsSource.parse(NO_DATA) == []


def test_assembly_builds_official_bill_articles_and_dedupes_across_keywords():
    sess = ApiSession([BILLS, BILLS])
    src = AssemblyBillsSource(keywords=["탄소", "녹색성장"], session=sess, api_key="", delay=0)
    arts = src.fetch()
    assert len(arts) == 1                                           # 제목 없는 행 제외, 같은 법안 중복 제거
    a = arts[0]
    assert a.source_type == "official" and a.agency == "국회(의원발의 법률안)"
    assert a.published == "2026-10-19T15:00:00+00:00"               # 2026-10-20 00:00 KST
    assert "박지혜의원" in a.summary and "계류" in a.summary
    assert a.url.startswith("http://likms.assembly.go.kr/bill/billDetail.do")


def test_assembly_sample_mode_without_key_requests_small_pages_and_never_sends_key():
    sess = ApiSession([BILLS])
    AssemblyBillsSource(keywords=["탄소"], session=sess, api_key="", delay=0).fetch()
    assert sess.params[0]["pSize"] == 5 and "KEY" not in sess.params[0]


def test_assembly_with_key_sends_it_and_requests_more():
    sess = ApiSession([BILLS])
    AssemblyBillsSource(keywords=["탄소"], session=sess, api_key="SECRET", delay=0).fetch()
    assert sess.params[0]["KEY"] == "SECRET" and sess.params[0]["pSize"] == 100


def test_assembly_failure_is_recorded_and_other_keywords_continue():
    class Flaky(ApiSession):
        def get(self, *a, **kw):
            if not self.params:
                self.params.append(1)
                raise ConnectionError("boom")
            return super().get(*a, **kw)

    src = AssemblyBillsSource(keywords=["a", "b"], session=Flaky([BILLS]), api_key="", delay=0)
    arts = src.fetch()
    assert src.failures == ["국회 법안 a"] and len(arts) == 1


# 레지스트리 --------------------------------------------------------------------------------
def test_registry_builds_known_sources_and_rejects_unknown():
    names = [s.name for s in build_sources(["google_news", "official_boards", "eu_presscorner", "assembly_bills"])]
    assert names == ["google_news", "official_boards", "eu_presscorner", "assembly_bills"]
    with pytest.raises(ValueError, match="알 수 없는 출처"):
        build_sources(["nope"])
