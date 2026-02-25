import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns

# 한글 깨짐 방지
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

class YeosuProject:
    def __init__(self):
        # 경로 설정
        self.base_path = r"c:\Users\a630838\Documents\trae_projects\data\row_data"
        self.save_path = r"c:\Users\a630838\Documents\trae_projects\data\final_result"
        
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)
            
    def data_load(self):
        # 1. 섬 기본 정보 (인구, 면적 등)
        island = pd.read_csv(os.path.join(self.base_path, "전라남도 여수시_유인도서현황_20241231.csv"), encoding='cp949')
        island.columns = [c.strip() for c in island.columns]
        
        # 2. 관광객 데이터
        tourist = pd.read_csv(os.path.join(self.base_path, "전라남도 여수시_관광객현황_20251218.csv"), encoding='cp949')
        
        # 3. 쓰레기 처리 비용 (공모전 경제성 논거용)
        waste_cost = pd.read_csv(os.path.join(self.base_path, "전라남도 여수시_연도별 음식물 쓰레기 처리비용_20231231.csv"), encoding='cp949')
        waste_cost.columns = ['연도', '비용']
        
        # 4. 배편 정보 (물류/접근성 체크)
        ferry = pd.read_csv(os.path.join(self.base_path, "전라남도 여수시_시민여객선 운임지원_여객선 항로 정보_20240613.csv"), encoding='cp949')
        
        print(f">> 데이터 {len(island)}건 로드 완료")
        return island, tourist, waste_cost, ferry

    def run_analysis(self):
        island, tourist, waste_cost, ferry = self.data_load()
        
        # --- 1. 섬별 예상 관광객 추정 ---
        # 여수 전체 관광객(최신값)을 섬 면적비율로 대략적으로 나눔
        total_tourist = tourist['관광객수합계'].iloc[0]
        island['visit_est'] = (island['면적(제곱킬로미터)'] / island['면적(제곱킬로미터)'].sum()) * total_tourist
        
        # --- 2. 쓰레기 발생량 계산 ---
        # 거주자(1kg/일), 관광객(1.5kg/일) 기준 - 실제보다 조금 넉넉하게 잡음
        island['waste_day'] = (island['인구'] * 1.0) + (island['visit_est'] / 365 * 1.5)
        
        # --- 3. 에너지 자립도 시뮬레이션 ---
        # 태양광 발전 잠재량 (면적의 0.5% 설치, 효율 15% 가정)
        island['solar_gen'] = island['면적(제곱킬로미터)'] * 1000000 * 0.005 * 4.0 * 365 * 0.15 / 1000
        # 에너지 수요 (1인당 연간 3MWh)
        island['energy_need'] = (island['인구'] + (island['visit_est']/365)) * 3.0
        island['energy_rate'] = (island['solar_gen'] / island['energy_need']) * 100
        
        # --- 4. 우선순위 지수 만들기 ---
        # 쓰레기는 많고, 에너지 자립은 낮고, 배편은 적은 곳 찾기
        # 배편 확인
        island['has_ferry'] = island['도서명'].apply(lambda x: 1 if any(ferry['항로명'].str.contains(x, na=False)) else 0)
        
        # 점수화 (쓰레기 50% + 에너지 30% + 배편부재 20%)
        island['score'] = (
            (island['waste_day'] / island['waste_day'].max() * 50) +
            ((100 - island['energy_rate'].clip(0, 100)) / 100 * 30) +
            ((1 - island['has_ferry']) * 20)
        )
        
        self.save_files(island, waste_cost)

    def save_files(self, df, cost_df):
        # 차트 그리기
        plt.figure(figsize=(12, 7))
        sns.scatterplot(data=df, x='waste_day', y='energy_rate', size='score', hue='score', palette='OrRd')
        
        # 상위 10개 섬 이름만 표시
        top_list = df.nlargest(10, 'score')
        for i, r in top_list.iterrows():
            plt.text(r['waste_day'], r['energy_rate'], r['도서명'], fontsize=10)
            
        plt.title('여수 섬 자원순환 거점 후보지 분석', fontsize=15)
        plt.xlabel('일일 예상 쓰레기량 (kg)')
        plt.ylabel('에너지 자립 잠재율 (%)')
        plt.savefig(os.path.join(self.save_path, '분석_결과_차트.png'))
        
        # 경제성 메모 작성
        avg_growth = (cost_df['비용'].iloc[-1] / cost_df['비용'].iloc[0]) ** (1/len(cost_df)) - 1
        est_2026 = cost_df['비용'].iloc[-1] * ((1 + avg_growth) ** 3) # 2026년 예상
        
        with open(os.path.join(self.save_path, '아이디어_기획_메모.txt'), 'w', encoding='utf-8') as f:
            f.write("여수 섬박람회 아이디어 공모전 참고자료\n")
            f.write("-" * 30 + "\n")
            f.write(f"* 음식물 쓰레기 처리비용 추세: 연평균 {avg_growth*100:.1f}%씩 증가 중\n")
            f.write(f"* 2026년 박람회 시점 예상 처리비용: 약 {est_2026/100000000:.1f} 억원 규모\n")
            f.write("* 자원순환 모델(에너지화) 도입 시 예산 절감 가능성 높음\n\n")
            f.write("* 최우선 검토 필요 섬:\n")
            for name in top_list['도서명'].head(5):
                f.write(f"  - {name}\n")
        
        df.to_csv(os.path.join(self.save_path, '최종_데이터_정리.csv'), index=False, encoding='cp949')
        print(">> 모든 결과물이 final_result 폴더에 저장되었습니다.")

if __name__ == "__main__":
    app = YeosuProject()
    app.run_analysis()
