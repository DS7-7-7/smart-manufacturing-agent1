@dataclass
class Order:
    order_id: str
    product: str
    quantity: int
    due_date: date
    priority: int          # 1(최우선) ~ 5(낮음)
    status: str = "pending"

@dataclass
class Material:
    material_id: str
    name: str
    unit: str
    current_stock: float
    reserved: float = 0.0

    @property
    def available(self) -> float:      # 가용 재고 = 현재고 - 선점분
        return round(self.current_stock - self.reserved, 3)