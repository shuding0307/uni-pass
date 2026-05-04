import os
import time
import glob
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

class GraduationCrawler:
    def __init__(self):
        # 🎯 다른 정보는 제외하고 오직 '영역별 이수 학점표'에만 집중합니다.
        self.target_url = "https://curriculum.kangwon.ac.kr/bbs/board.php?bo_table=sub2_5"
        
        # 프로젝트 루트 경로 설정 (uni-pass/data/raw_requirements)
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        self.download_dir = os.path.join(self.base_dir, "data", "raw_requirements")
        
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    def _setup_driver(self):
        """Chrome 드라이버 설정 및 다운로드 자동화 세팅"""
        chrome_options = webdriver.ChromeOptions()
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # 처음에는 화면을 보면서 확인해야 하니 headless는 꺼둡니다.
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        return driver

    def _rename_latest_file(self, new_filename):
        """방금 다운로드된 파일을 학번별 이름으로 변경"""
        time.sleep(3) # 다운로드 완료 대기
        list_of_files = glob.glob(os.path.join(self.download_dir, '*'))
        if not list_of_files: return
        
        latest_file = max(list_of_files, key=os.path.getctime)
        if not latest_file.endswith('.crdownload'):
            new_file_path = os.path.join(self.download_dir, new_filename)
            if os.path.exists(new_file_path): os.remove(new_file_path)
            os.rename(latest_file, new_file_path)
            print(f"   [완료] {new_filename} 저장 성공")

    def run_credit_crawling(self, target_years=range(2019, 2027)):
        """URL 검색 파라미터를 활용한 초고속 크롤링"""
        driver = self._setup_driver()
        wait = WebDriverWait(driver, 10)

        print(f"========== 강원대 이수학점표 수집 시작 ==========")
        
        try:
            for year in target_years:
                # 💡 [핵심] URL 뒤에 &stx=년도 를 붙여서 즉시 검색 결과 페이지로 직행!
                search_url = f"{self.target_url}&stx={year}"
                print(f"\n -> {year}학년도 검색 페이지 접속 중...")
                driver.get(search_url)
                time.sleep(2)
                
                try:
                    # 지인님이 완벽하게 찾아주신 TODO 3 (파일 아이콘 주소) 그대로 사용!
                    icon_selector = "#fboardlist > div.tbl_head01.tbl_wrap.pc_notice-dis > table > tbody > tr:nth-child(1) > td:nth-child(3) > a > img"
                    download_icon = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, icon_selector)))
                    
                    # 파일 아이콘 클릭
                    driver.execute_script("arguments[0].click();", download_icon)
                    
                    # 파일 이름 변경
                    self._rename_latest_file(f"이수학점표_{year}학년도.pdf")
                    
                except Exception as e:
                    print(f"   [경고] {year}학년도 글이 존재하지 않거나 아이콘을 찾을 수 없습니다.")
                    
        finally:
            driver.quit()
            print("\n========== 수집 프로세스 종료 ==========")

if __name__ == "__main__":
    crawler = GraduationCrawler()
    # 💡 우선 2025학년도 하나만 테스트해보고, 잘 되면 숫자를 늘려보세요!
    crawler.run_credit_crawling()