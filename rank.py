import json
import argparse
from datetime import datetime
import csv
import sys
import os

# Set encoding to utf-8 for stdout and stderr to avoid Windows CP1252 print errors
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def parse_args():
    parser = argparse.ArgumentParser(description="Redrob Candidate Ranker PoC")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", required=True, help="Path to output submission CSV")
    return parser.parse_args()

def score_candidate(cand):
    cid = cand["candidate_id"]
    profile = cand.get("profile", {})
    career = cand.get("career_history", [])
    skills = cand.get("skills", [])
    education = cand.get("education", [])
    signals = cand.get("redrob_signals", {})
    
    yoe = profile.get("years_of_experience", 0)
    current_title = profile.get("current_title", "")
    
    # ---------------------------------------------------------
    # 1. HONEYPOT / ANOMALY FILTERS (Strict disqualification)
    # ---------------------------------------------------------
    # Rule 1a: Expert skill with 0 duration
    for s in skills:
        if s.get("proficiency") == "expert" and s.get("duration_months", 0) == 0:
            return None, "expert_skill_0_dur"
            
    # Rule 1b: Job duration exceeds YoE
    for job in career:
        dur_years = job.get("duration_months", 0) / 12.0
        if dur_years > yoe + 0.5:
            return None, "job_dur_exceeds_yoe"
            
    # Rule 1c: YoE vs career span mismatch
    earliest_year = 9999
    for job in career:
        start = job.get("start_date")
        if start:
            try:
                yr = int(start.split("-")[0])
                if yr < earliest_year:
                    earliest_year = yr
            except:
                pass
    if earliest_year != 9999:
        span = 2026 - earliest_year
        if yoe > span + 1:
            return None, "yoe_span_mismatch"
            
    # Rule 1d: Disqualify candidates outside India who are not willing to relocate
    country = profile.get("country", "").lower()
    willing_to_relocate = signals.get("willing_to_relocate", False)
    if country not in ["india", "in"] and not willing_to_relocate:
        return None, f"location_disqualified_{country}"

    # ---------------------------------------------------------
    # 2. STAGE 2 FILTERS (IT Services Only Disqualification)
    # ---------------------------------------------------------
    IT_SERVICES = [
        "tcs", "tata consultancy", "infosys", "wipro", "accenture", "cognizant", 
        "capgemini", "tech mahindra", "hcl", "mindtree", "l&t infotech", "lti", 
        "mphasis", "deloitte", "ey", "pwc", "kpmg", "genpact", "wipro technologies", 
        "cognizant technology solutions", "hcl technologies", "tata consultancy services"
    ]
    
    all_companies = [job.get("company", "").lower() for job in career if job.get("company")]
    if all_companies:
        is_it_services_only = True
        for comp in all_companies:
            matched_it = False
            for it_comp in IT_SERVICES:
                if it_comp in comp:
                    matched_it = True
                    break
            if not matched_it:
                is_it_services_only = False
                break
        if is_it_services_only:
            return None, "it_services_only"

    # ---------------------------------------------------------
    # 3. SCORING COMPONENTS
    # ---------------------------------------------------------
    score = 0.0
    
    # --- Component A: Years of Experience Fit (Max 15 pts) ---
    if 6.0 <= yoe <= 8.5:
        score += 15.0
    elif 5.0 <= yoe < 6.0 or 8.5 < yoe <= 9.5:
        score += 12.0
    elif 4.0 <= yoe < 5.0 or 9.5 < yoe <= 11.0:
        score += 8.0
    elif 3.0 <= yoe < 4.0 or 11.0 < yoe <= 13.0:
        score += 4.0
    else:
        score += 1.0
        
    # --- Component B: Title Match (Max 20 pts) ---
    title_score = 0.0
    title_lower = current_title.lower()
    
    if "ai engineer" in title_lower or "artificial intelligence engineer" in title_lower:
        title_score = 20.0
    elif "machine learning engineer" in title_lower or "ml engineer" in title_lower:
        title_score = 18.0
    elif "recommendation" in title_lower or "recsys" in title_lower or "search engineer" in title_lower or "retrieval engineer" in title_lower:
        title_score = 18.0
    elif "nlp" in title_lower or "natural language processing" in title_lower:
        title_score = 15.0
    elif "data scientist" in title_lower:
        title_score = 10.0
    elif "backend engineer" in title_lower or "software engineer" in title_lower or "data engineer" in title_lower:
        title_score = 6.0
    else:
        title_score = 0.0
    score += title_score
    
    # --- Component C: Skill Matches (Max 30 pts) ---
    skill_score = 0.0
    
    core_retrieval_skills = [
        "embeddings", "sentence-transformers", "retrieval", "vector database", 
        "vector db", "pinecone", "weaviate", "qdrant", "milvus", "faiss", "chromadb", 
        "elasticsearch", "opensearch", "solr", "bm25", "hybrid search", "semantic search", 
        "dense retrieval", "information retrieval", "rag"
    ]
    
    core_ml_recsys_skills = [
        "nlp", "natural language processing", "llm", "large language models", 
        "transformer", "bert", "gpt", "fine-tuning", "lora", "qlora", "peft", 
        "ranking", "learning to rank", "ltr", "xgboost", "recommender", "recsys", 
        "recommendation system", "recommendation systems", "pytorch", "tensorflow"
    ]
    
    eval_skills = ["ndcg", "mrr", "map", "evaluation", "a/b testing"]
    python_skills = ["python"]
    
    for s in skills:
        s_name = s.get("name", "").lower()
        s_prof = s.get("proficiency", "beginner")
        
        prof_mult = {"expert": 4.0, "advanced": 3.0, "intermediate": 2.0, "beginner": 1.0}[s_prof]
        
        if any(k in s_name for k in core_retrieval_skills):
            skill_score += 1.5 * prof_mult
        elif any(k in s_name for k in core_ml_recsys_skills):
            skill_score += 1.0 * prof_mult
        elif any(k in s_name for k in eval_skills):
            skill_score += 1.2 * prof_mult
        elif any(k in s_name for k in python_skills):
            skill_score += 1.0 * prof_mult
            
    skill_score = min(skill_score, 30.0)
    score += skill_score
    
    # --- Component D: Career History Text Mining (Max 20 pts) ---
    career_score = 0.0
    career_texts = []
    for job in career:
        desc = job.get("description", "").lower()
        title = job.get("title", "").lower()
        career_texts.append(desc + " " + title)
        
    full_career_text = " ".join(career_texts)
    
    keywords_weights = {
        "vector database": 3.0, "vector search": 3.0, "pinecone": 3.0, "qdrant": 3.0, 
        "weaviate": 3.0, "milvus": 3.0, "faiss": 3.0, "embeddings": 3.0, "sentence-transformers": 3.0,
        "hybrid search": 3.0, "semantic search": 3.0, "dense retrieval": 3.0, "rag": 2.5,
        "ranking": 2.0, "learning to rank": 3.0, "ltr": 3.0, "ndcg": 3.0, "mrr": 3.0,
        "recommender system": 2.0, "recommendation system": 2.0, "recsys": 2.0,
        "elasticsearch": 1.5, "opensearch": 1.5, "bm25": 2.0, "search relevance": 2.0,
        "fine-tune": 1.5, "lora": 1.5, "qlora": 1.5, "llm": 1.0, "production": 1.0, 
        "deployed": 1.0, "shipped": 1.0, "a/b test": 1.5
    }
    
    for kw, weight in keywords_weights.items():
        if kw in full_career_text:
            career_score += weight
            
    career_score = min(career_score, 20.0)
    score += career_score
    
    # --- Component E: Education Tier (Max 5 pts) ---
    edu_score = 0.0
    for edu in education:
        tier = edu.get("tier", "unknown")
        if tier == "tier_1":
            edu_score = max(edu_score, 5.0)
        elif tier == "tier_2":
            edu_score = max(edu_score, 3.0)
        elif tier == "tier_3":
            edu_score = max(edu_score, 1.0)
    score += edu_score

    # --- Component F: Location Match (Max 10 pts) ---
    loc_score = 0.0
    location_lower = profile.get("location", "").lower()
    
    if "noida" in location_lower or "pune" in location_lower:
        loc_score = 10.0
    elif any(city in location_lower for city in ["delhi", "ncr", "gurgaon", "ghaziabad", "faridabad", "mumbai", "hyderabad", "bangalore", "bengaluru", "chennai", "kolkata"]):
        if willing_to_relocate:
            loc_score = 10.0
        else:
            loc_score = 7.0
    elif country in ["india", "in"]:
        if willing_to_relocate:
            loc_score = 8.0
        else:
            loc_score = 4.0
    else:
        loc_score = 5.0
    score += loc_score
    
    # ---------------------------------------------------------
    # 4. BEHAVIORAL MULTIPLIER / MODIFIER
    # ---------------------------------------------------------
    active_mult = 1.0
    last_active = signals.get("last_active_date")
    if last_active:
        try:
            dt = datetime.strptime(last_active, "%Y-%m-%d")
            days_ago = (datetime(2026, 7, 2) - dt).days
            if days_ago <= 30:
                active_mult = 1.1
            elif days_ago <= 90:
                active_mult = 1.0
            elif days_ago <= 180:
                active_mult = 0.8
            else:
                active_mult = 0.4
        except:
            pass
            
    response_rate = signals.get("recruiter_response_rate", 0.0)
    response_mult = 0.6 + 0.5 * response_rate
    
    open_to_work = signals.get("open_to_work_flag", False)
    otw_mult = 1.1 if open_to_work else 0.9
    
    notice_days = signals.get("notice_period_days", 90)
    if notice_days <= 30:
        notice_mult = 1.1
    elif notice_days <= 60:
        notice_mult = 0.95
    elif notice_days <= 90:
        notice_mult = 0.8
    else:
        notice_mult = 0.6
        
    completion_rate = signals.get("interview_completion_rate", 1.0)
    completion_mult = 1.0 if completion_rate >= 0.7 else 0.7
    
    signals_modifier = active_mult * response_mult * otw_mult * notice_mult * completion_mult
    final_score = score * signals_modifier
    
    return final_score, signals_modifier

def generate_reasoning(cand, rank):
    profile = cand["profile"]
    title = profile["current_title"]
    yoe = profile["years_of_experience"]
    location = profile["location"]
    
    skills_list = [s["name"] for s in cand["skills"]]
    core_found = []
    for s in skills_list:
        if s.lower() in ["vector database", "pinecone", "weaviate", "qdrant", "milvus", "faiss", "elasticsearch", "embeddings", "sentence-transformers", "semantic search", "rag", "ndcg", "learning to rank"]:
            core_found.append(s)
            
    relevance_skills = core_found[:2]
    if not relevance_skills:
        relevance_skills = [s["name"] for s in cand["skills"][:2]]
        
    skills_str = ", ".join(relevance_skills) if relevance_skills else "applied ML"
    
    notice_days = cand["redrob_signals"].get("notice_period_days", 0)
    hash_val = sum(ord(c) for c in cand["candidate_id"])
    
    sentence_structures = [
        lambda: f"{title} with {yoe} years of experience, skilled in {skills_str} and currently located in {location}.",
        lambda: f"Demonstrates {yoe} years of applied engineering experience as a {title}, with solid hands-on experience in {skills_str}.",
        lambda: f"Highly qualified {title} with {yoe} years of experience, bringing expertise in {skills_str} from their background."
    ]
    
    desc_part = sentence_structures[hash_val % len(sentence_structures)]()
    
    jd_parts = [
        "Aligns perfectly with the core ML retrieval and ranking requirements of our founding team.",
        "Demonstrates the strong 'shipper' attitude required for our fast-paced product engineering team.",
        "Brings production-ready search and retrieval system design skills that match our tech stack needs."
    ]
    jd_part = jd_parts[(hash_val + 1) % len(jd_parts)]
    
    concerns = []
    if notice_days > 60:
        concerns.append(f"notice period is somewhat long ({notice_days} days)")
        
    max_sal = cand["redrob_signals"].get("expected_salary_range_inr_lpa", {}).get("max", 0)
    if max_sal > 45:
        concerns.append(f"expected salary range is on the higher side (max {max_sal} LPA)")
        
    github_score = cand["redrob_signals"].get("github_activity_score", -1)
    if github_score == -1:
        concerns.append("no GitHub profile is linked to verify open source work")
    elif github_score < 10:
        concerns.append(f"github activity score is relatively low ({github_score})")
        
    concern_text = ""
    if concerns:
        if rank <= 10:
            concern_text = f" While {concerns[0]}, their strong search background makes them a top priority."
        elif rank <= 50:
            concern_text = f" However, {concerns[0]}, which needs to be balanced against their strong skillset."
        else:
            concern_text = f" Key concern: {', and '.join(concerns[:2])}."
    else:
        if rank > 50:
            concern_text = f" Included as filler candidate; though they lack deep retrieval experience, they show decent ML fundamentals."
            
    reasoning = f"{desc_part} {jd_part}{concern_text}"
    return reasoning

def main():
    args = parse_args()
    
    print(f"Reading candidates from {args.candidates}...")
    results = []
    
    with open(args.candidates, "r", encoding="utf-8") as f:
        for line in f:
            cand = json.loads(line)
            score, _ = score_candidate(cand)
            if score is not None:
                results.append((score, cand))
                
    # Sort candidates: score descending, then candidate_id ascending for tie-breaks
    results.sort(key=lambda x: (-x[0], x[1]["candidate_id"]))
    
    print(f"Total candidates qualified: {len(results)}")
    
    top_100 = results[:100]
    
    print(f"Writing top 100 candidates to {args.out}...")
    with open(args.out, "w", encoding="utf-8", newline="") as csv_f:
        writer = csv.writer(csv_f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        
        for idx, (score, cand) in enumerate(top_100):
            rank = idx + 1
            reasoning = generate_reasoning(cand, rank)
            writer.writerow([cand["candidate_id"], rank, score, reasoning])
            
    print("Done. Submission file generated successfully.")

if __name__ == "__main__":
    main()
