import re
import json
import os

def parse_starforce_text(raw_text):
    lines = [l.strip() for l in raw_text.strip().split('\n') if l.strip()]
    if not lines: return

    # 0. 첫 줄에서 이벤트 이름 추출 및 정제
    first_line = lines[0]
    if "미적용" in first_line:
        event_id = "no_event"
    else:
        # 파일명으로 쓰기 좋게 특수문자 제거 및 공백 변경
        event_id = re.sub(r'[^\w\s%]', '', first_line).strip().replace(" ", "_")

    # 1. 메타 데이터 추출 (기간)
    period_match = re.search(r"∗ (.*?) 확률입니다", raw_text)
    period_text = period_match.group(1).replace(" 점검 이후", "").replace(" 점검 이전까지", "").replace(" ", "") if period_match else "unknown"
    
    # 날짜 추출 (파일 접두어 YYYYMMDD)
    date_match = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", raw_text)
    file_prefix = f"{date_match.group(1)}{int(date_match.group(2)):02d}{int(date_match.group(3)):02d}" if date_match else "stats"

    # 2. 스타캐치 O / X 섹션 분리
    parts = re.split(r"(스타캐치 [OX])", raw_text)
    
    # 보수적인 정규식
    row_re = re.compile(r"(성공|실패\s\(유지\)|파괴)\s*([\d,]+?)\s*(\d+\.?\d*)%\s*(\d*\.?\d*)%?")
    
    current_mode = None
    for part in parts:
        part = part.strip()
        if not part: continue
        
        if part in ["스타캐치 O", "스타캐치 X"]:
            current_mode = part
            continue
            
        if current_mode and ("강화 단계" in part or "항목" in part):
            records = []
            segment_lines = [line.strip() for line in part.split('\n') if line.strip()]
            
            i = 0
            while i < len(segment_lines):
                line = segment_lines[i]
                star_match = re.search(r"(\d+)성", line)
                
                if star_match:
                    star = int(star_match.group(1))
                    current_record = {
                        "star": star, "total_n": 0, 
                        "success_n": 0, "success_p_target": 0.0, "success_p_actual": 0.0,
                        "fail_n": 0, "fail_p_target": 0.0, "fail_p_actual": 0.0,
                        "boom_n": 0, "boom_p_target": 0.0, "boom_p_actual": 0.0
                    }
                    
                    while i < len(segment_lines):
                        curr_line = segment_lines[i]
                        new_star_check = re.search(r"(\d+)성", curr_line)
                        if new_star_check and int(new_star_check.group(1)) != star:
                            break
                        
                        m = row_re.search(curr_line)
                        if m:
                            res_type, count_str, target_p_str, actual_p_str = m.groups()
                            count = int(count_str.replace(',', ''))
                            
                            if not actual_p_str and i + 1 < len(segment_lines):
                                next_line = segment_lines[i+1]
                                next_m = re.search(r"(\d+\.?\d*)%", next_line)
                                if next_m:
                                    actual_p_str = next_m.group(1)
                                    i += 1 
                            
                            current_record["total_n"] += count
                            key_map = {"성공": "success", "실패 (유지)": "fail", "파괴": "boom"}
                            prefix = key_map.get(res_type)
                            if prefix:
                                current_record[f"{prefix}_n"] = count
                                current_record[f"{prefix}_p_target"] = float(target_p_str) / 100
                                current_record[f"{prefix}_p_actual"] = float(actual_p_str) / 100 if actual_p_str else 0.0
                        i += 1
                    
                    for prefix in ["success", "fail", "boom"]:
                        target_p_key = f"{prefix}_p_target"
                        actual_p_key = f"{prefix}_p_actual"
                        p = current_record.get(target_p_key, 0.0)
                        n = current_record["total_n"]
                        if n > 0 and 0 < p < 1:
                            expected_std = (p * (1 - p) / n) ** 0.5
                            z_score = (current_record[actual_p_key] - p) / expected_std
                            current_record[f"{prefix}_expected_std"] = expected_std
                            current_record[f"{prefix}_z_score"] = z_score
                        else:
                            current_record[f"{prefix}_expected_std"] = 0.0
                            current_record[f"{prefix}_z_score"] = 0.0

                    # Skip empty/placeholder stars (prevents total_n==0 rows from polluting analytics)
                    if current_record["total_n"] > 0:
                        records.append(current_record)
                    continue 
                i += 1
            
            suffix = "catch_on" if "O" in current_mode else "catch_off"
            if not os.path.exists("audit_data"): os.makedirs("audit_data")
                
            filename = f"audit_data/{file_prefix}_{event_id}_{suffix}.json"
            
            output = {
                "meta": {
                    "title": f"Starforce Stats {first_line}",
                    "period": period_text,
                    "event": first_line,
                    "star_catch": "O" in current_mode
                },
                "records": records
            }
            
            with open(filename, "w", encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"Saved: {filename}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding='utf-8') as f:
            parse_starforce_text(f.read())
