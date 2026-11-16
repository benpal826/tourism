"""config.SOURCES 의 이름을 수집기 객체로 바꿔 준다. 새 출처는 여기에 한 줄만 등록하면 된다."""
import config
from .assembly import AssemblyBillsSource
from .base import Source
from .boards import OfficialBoardSource
from .eu import EuPresscornerSource
from .google_news import GoogleNewsSource
from .http import PoliteClient


def build_sources(names: list[str] | None = None) -> list[Source]:
    names = names if names is not None else config.SOURCES
    client = PoliteClient()   # 공식 사이트들이 간격·robots 설정을 공유한다
    factories = {
        "google_news": lambda: GoogleNewsSource(),
        "official_boards": lambda: OfficialBoardSource(client=client),
        "eu_presscorner": lambda: EuPresscornerSource(client=client),
        "assembly_bills": lambda: AssemblyBillsSource(),
    }
    unknown = [n for n in names if n not in factories]
    if unknown:
        raise ValueError(f"알 수 없는 출처: {', '.join(unknown)} (사용 가능: {', '.join(factories)})")
    return [factories[n]() for n in names]
