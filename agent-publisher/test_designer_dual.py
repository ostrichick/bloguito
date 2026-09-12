from agents.designer import DesignerAgent

def test():
    d = DesignerAgent()
    print("--- Test 1 ---")
    p1 = d.generate_image("2026 트로트 페스티벌 티켓 예매", "공연/콘서트 예매", "트로트")
    print("Run 1 result:", p1)
    print("\n--- Test 2 ---")
    p2 = d.generate_image("임산부 교통비 지원 신청 방법", "정부 복지/지원금", "교통비 지원")
    print("Run 2 result:", p2)

if __name__ == "__main__":
    test()
