"""NiceGUI CAR SCOUT application — three-layer architecture.

Layers
------
1. Persistence   : SQLite via SQLAlchemy ORM  (CarRecord, Database)
2. Business Logic: CarService                  (validation + operations)
3. Presentation  : NiceGUI UI classes          (CarScoutApp)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

# ── ORM ──────────────────────────────────────────────────────────────────────
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ── NiceGUI ──────────────────────────────────────────────────────────────────
from nicegui import ui


# =============================================================================
# 1. PERSISTENCE LAYER
# =============================================================================

class Base(DeclarativeBase):
    pass


class CarRecord(Base):
    """ORM model — maps to the 'cars' table in SQLite."""

    __tablename__ = "cars"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    brand    = Column(String,  nullable=False)
    model    = Column(String,  nullable=False)
    year     = Column(Integer, nullable=False)
    km       = Column(Integer, nullable=False)
    trans    = Column(String,  nullable=False)   # 'manual' | 'automatic'
    price    = Column(Float,   nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "brand": self.brand, "model": self.model,
            "year": self.year, "km": self.km, "trans": self.trans,
            "price": self.price,
        }


class Database:
    """Thin wrapper around the SQLAlchemy engine / session factory."""

    def __init__(self, url: str = "sqlite:///cars.db") -> None:
        self._engine = create_engine(url, echo=False)
        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    def session(self) -> Session:
        return self._Session()


# =============================================================================
# 2. BUSINESS LOGIC / APPLICATION LAYER
# =============================================================================

class CarService:
    """All business operations on car data. UI knows nothing about SQL."""

    def __init__(self, db: Database) -> None:
        self._db = db

    # ── validation helpers ────────────────────────────────────────────────────

    @staticmethod
    def validate_car(brand: str, model: str, year: str, km: str,
                     trans: str, price: str) -> list[str]:
        """Return a list of human-readable error messages (empty = valid)."""
        errors: list[str] = []
        current_year = datetime.now().year

        if not brand.strip():
            errors.append("Brand cannot be empty.")
        if not model.strip():
            errors.append("Model cannot be empty.")

        try:
            y = int(year)
            if y < 1886 or y > current_year:
                errors.append(f"Year must be between 1886 and {current_year}.")
        except ValueError:
            errors.append("Year must be a whole number.")

        try:
            k = int(km)
            if k < 0:
                errors.append("Kilometres cannot be negative.")
        except ValueError:
            errors.append("Kilometres must be a whole number.")

        if trans not in ("manual", "automatic"):
            errors.append("Transmission must be 'manual' or 'automatic'.")

        try:
            p = float(price)
            if p < 0:
                errors.append("Price cannot be negative.")
        except ValueError:
            errors.append("Price must be a number (e.g. 12500.00).")

        return errors

    # ── CRUD operations ───────────────────────────────────────────────────────

    def get_all(self) -> list[dict]:
        with self._db.session() as s:
            return [c.to_dict() for c in s.query(CarRecord).all()]

    def search_by_max_price(self, max_price: float) -> list[dict]:
        with self._db.session() as s:
            rows = s.query(CarRecord).filter(CarRecord.price <= max_price).all()
            return [c.to_dict() for c in rows]

    def add(self, brand: str, model: str, year: int, km: int,
            trans: str, price: float) -> CarRecord:
        with self._db.session() as s:
            car = CarRecord(brand=brand, model=model, year=year,
                            km=km, trans=trans, price=price)
            s.add(car)
            s.commit()
            s.refresh(car)
            return car

    def delete(self, car_id: int) -> bool:
        with self._db.session() as s:
            car = s.get(CarRecord, car_id)
            if car is None:
                return False
            s.delete(car)
            s.commit()
            return True


# =============================================================================
# 3. PRESENTATION LAYER  (NiceGUI)
# =============================================================================

class CarScoutApp:
    """
    All NiceGUI UI components live here.
    State is held in server-side Python objects (ui.* widgets).
    The browser is a thin rendering client — it holds no business logic.
    """

    # ── colour palette ────────────────────────────────────────────────────────
    ACCENT   = "#E63946"   # red
    DARK_BG  = "#1A1A2E"
    CARD_BG  = "#16213E"
    TEXT     = "#EAEAEA"
    MUTED    = "#8892A4"
    SUCCESS  = "#2EC4B6"

    def __init__(self, service: CarService) -> None:
        self._svc = service
        self._build_ui()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _notify(self, msg: str, kind: str = "positive") -> None:
        ui.notify(msg, type=kind, position="top-right", timeout=3000)

    def _price_fmt(self, p: float) -> str:
        return f"CHF {p:,.0f}"

    # ── car table ─────────────────────────────────────────────────────────────

    def _refresh_table(self, rows: Optional[list[dict]] = None) -> None:
        """Re-render the cars table with *rows* (defaults to all cars)."""
        if rows is None:
            rows = self._svc.get_all()
        self._table_area.clear()
        with self._table_area:
            if not rows:
                ui.label("No cars found.").classes("text-gray-400 italic p-4")
                return
            with ui.element("table").classes("w-full border-collapse"):
                # header
                with ui.element("thead"):
                    with ui.element("tr").classes("text-left"):
                        for col in ["Brand", "Model", "Year", "KM",
                                    "Transmission", "Price", ""]:
                            ui.element("th").classes(
                                "px-4 py-3 text-xs uppercase tracking-widest "
                                "text-gray-400 border-b border-gray-700"
                            ).text(col)
                # body
                with ui.element("tbody"):
                    for car in rows:
                        with ui.element("tr").classes(
                            "border-b border-gray-800 hover:bg-gray-800/40 "
                            "transition-colors"
                        ):
                            for val in [
                                car["brand"], car["model"], car["year"],
                                f"{car['km']:,} km", car["trans"].capitalize(),
                                self._price_fmt(car["price"]),
                            ]:
                                ui.element("td").classes(
                                    "px-4 py-3 text-sm"
                                ).text(str(val))
                            # delete button
                            with ui.element("td").classes("px-4 py-3"):
                                cid = car["id"]
                                ui.button(
                                    icon="delete",
                                    on_click=lambda _, i=cid: self._delete_car(i),
                                ).props("flat round color=negative size=sm")

    def _delete_car(self, car_id: int) -> None:
        ok = self._svc.delete(car_id)
        if ok:
            self._notify("Car deleted.", "warning")
            self._refresh_table()
        else:
            self._notify("Car not found.", "negative")

    # ── add-car form ──────────────────────────────────────────────────────────

    def _submit_add(self) -> None:
        errors = CarService.validate_car(
            self._inp_brand.value, self._inp_model.value,
            self._inp_year.value, self._inp_km.value,
            self._sel_trans.value, self._inp_price.value,
        )
        if errors:
            self._notify("\n".join(errors), "negative")
            return

        self._svc.add(
            brand=self._inp_brand.value.strip(),
            model=self._inp_model.value.strip(),
            year=int(self._inp_year.value),
            km=int(self._inp_km.value),
            trans=self._sel_trans.value,
            price=float(self._inp_price.value),
        )
        self._notify("Car added successfully!", "positive")

        # clear form
        for field in [self._inp_brand, self._inp_model, self._inp_year,
                      self._inp_km, self._inp_price]:
            field.value = ""
        self._sel_trans.value = "manual"

        # refresh table
        self._refresh_table()
        self._tabs.set_value("all")   # jump to the list tab

    # ── search ────────────────────────────────────────────────────────────────

    def _submit_search(self) -> None:
        try:
            max_p = float(self._inp_search_price.value)
        except ValueError:
            self._notify("Please enter a valid price.", "negative")
            return
        results = self._svc.search_by_max_price(max_p)
        self._refresh_table(results)
        self._notify(f"{len(results)} car(s) found.", "info")
        self._tabs.set_value("all")

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        ui.add_head_html(
            '<link href="https://fonts.googleapis.com/css2?'
            'family=Rajdhani:wght@500;700&family=Inter:wght@300;400;500&display=swap" '
            'rel="stylesheet">'
        )
        ui.add_css(f"""
            body {{
                background: {self.DARK_BG};
                color: {self.TEXT};
                font-family: 'Inter', sans-serif;
            }}
            .app-title {{
                font-family: 'Rajdhani', sans-serif;
                font-weight: 700;
                font-size: 2.4rem;
                letter-spacing: .05em;
                color: {self.ACCENT};
            }}
            .card {{
                background: {self.CARD_BG};
                border: 1px solid #2a2f45;
                border-radius: 12px;
                padding: 1.5rem;
            }}
            .section-label {{
                font-family: 'Rajdhani', sans-serif;
                font-size: 1.1rem;
                font-weight: 700;
                letter-spacing: .1em;
                text-transform: uppercase;
                color: {self.ACCENT};
                margin-bottom: .75rem;
            }}
        """)

        with ui.column().classes("w-full min-h-screen p-6 gap-6"):
            # header
            with ui.row().classes("items-center gap-4"):
                ui.icon("directions_car", size="2.5rem").style(
                    f"color:{self.ACCENT}")
                ui.label("CAR SCOUT").classes("app-title")

            # tabs
            self._tabs = ui.tabs().classes("w-full").props(
                f"active-color=red indicator-color=red"
            )
            with self._tabs:
                ui.tab("all",    label="All Cars",   icon="list")
                ui.tab("add",    label="Add Car",    icon="add_circle")
                ui.tab("search", label="Search",     icon="search")

            with ui.tab_panels(self._tabs, value="all").classes("w-full"):

                # ── ALL CARS panel ────────────────────────────────────────────
                with ui.tab_panel("all"):
                    with ui.element("div").classes("card"):
                        with ui.row().classes(
                            "items-center justify-between mb-4"
                        ):
                            ui.label("Fleet Overview").classes("section-label")
                            ui.button(
                                "Refresh", icon="refresh",
                                on_click=lambda: self._refresh_table()
                            ).props("outline color=grey-5 size=sm")

                        self._table_area = ui.column().classes("w-full overflow-x-auto")
                        self._refresh_table()

                # ── ADD CAR panel ─────────────────────────────────────────────
                with ui.tab_panel("add"):
                    with ui.element("div").classes("card max-w-xl"):
                        ui.label("Add New Car").classes("section-label")

                        self._inp_brand = ui.input(
                            label="Brand", placeholder="e.g. Toyota"
                        ).classes("w-full")
                        self._inp_model = ui.input(
                            label="Model", placeholder="e.g. Corolla"
                        ).classes("w-full")

                        with ui.row().classes("w-full gap-4"):
                            self._inp_year = ui.input(
                                label="Year", placeholder=str(datetime.now().year)
                            ).classes("flex-1")
                            self._inp_km = ui.input(
                                label="Kilometres", placeholder="0"
                            ).classes("flex-1")

                        self._sel_trans = ui.select(
                            ["manual", "automatic"],
                            label="Transmission",
                            value="manual",
                        ).classes("w-full")

                        self._inp_price = ui.input(
                            label="Price (CHF)", placeholder="e.g. 12500"
                        ).classes("w-full")

                        ui.button(
                            "Add Car", icon="add",
                            on_click=self._submit_add,
                        ).props("color=red").classes("mt-4 w-full")

                # ── SEARCH panel ──────────────────────────────────────────────
                with ui.tab_panel("search"):
                    with ui.element("div").classes("card max-w-md"):
                        ui.label("Search by Budget").classes("section-label")
                        self._inp_search_price = ui.input(
                            label="Max price (CHF)", placeholder="e.g. 20000"
                        ).classes("w-full")
                        ui.button(
                            "Find Cars", icon="search",
                            on_click=self._submit_search,
                        ).props("color=red").classes("mt-4 w-full")
                        ui.label(
                            "Results will appear in the 'All Cars' tab."
                        ).classes("text-gray-400 text-sm mt-2 italic")


# =============================================================================
# ENTRY POINT
# =============================================================================

def main() -> None:
    db      = Database()          # persistence layer
    service = CarService(db)      # business logic layer
    CarScoutApp(service)          # presentation layer  (builds UI on init)

    ui.run(title="Car Scout", dark=True, port=8080)


if __name__ in {"__main__", "__mp_main__"}:
    main()
    