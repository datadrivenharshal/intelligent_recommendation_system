# SHL Intelligent Recommendation System (RAG-Based)

## 📌 Project Overview
This project aims to build an **Intelligent Recommendation System** using **Retrieval-Augmented Generation (RAG)** to suggest relevant **SHL Individual Test Assessments** based on:
- Natural language queries
- Job descriptions (JD)
- JD URLs

The system retrieves and ranks assessments from the SHL catalog and provides **5–10 most relevant recommendations** with **name + URL**.

---


**Steps:**
1. **Scraping** → Crawl SHL catalog for Individual Test Solutions.
2. **Embedding** → Convert catalog items into vector representations.
3. **Retrieval** → Hybrid search (BM25 + FAISS) for candidate assessments.
4. **Reranking** → Apply filters (duration, K/P balance) and cross-encoder reranker.
5. **LLM Orchestration** → Parse query, enforce balance, format recommendations.
6. **API** → `/health` and `/recommend` endpoints.
7. **Frontend** → Streamlit UI for user interaction.
8. **Evaluation** → Compute **Mean Recall@10** using Train-Set.

---

## 📂 Repo Layout
```
.
├─ data/
│  ├─ catalog.db               # SQLite DB with scraped items
│  ├─ shl_catalog_raw.jsonl    # Raw scraped data backup
│  ├─ embeddings/faiss_index/  # Vector store artifacts
│  └─ ground_truth/
│     ├─ train_pairs.csv       # Train-Set
│     └─ test_queries.csv      # Test-Set
├─ scraping/
│  └─ shl_scraper.py           # SHL catalog scraper
├─ indexing/
│  ├─ build_index.py           # Embedding + FAISS index builder
│  └─ schema.py                # Data schema definitions
├─ retrieval/
│  ├─ hybrid_retrieve.py       # BM25 + FAISS retrieval logic
│  ├─ rerank.py                # Cross-encoder reranker + rules
│  └─ rules.py                 # Duration/type filters, K/P balance
├─ api/
│  └─ main.py                  # FastAPI endpoints
├─ app/
│  └─ ui.py                    # Streamlit frontend
├─ eval/
│  └─ evaluate_recall.ipynb    # Mean Recall@10 evaluation
├─ .env.example                # Environment variables template
├─ requirements.txt            # Dependencies
└─ README.md                   # Project documentation
```

---

## 🛠 Tools & Libraries
- **LangChain**: Orchestration of LLM and retrieval chains.
- **FAISS**: Efficient vector similarity search.
- **sentence-transformers**: Cross-encoder reranking for better relevance.
- **FastAPI**: API endpoints for recommendation service.
- **Streamlit**: Frontend for user interaction.
- **BeautifulSoup (bs4)**: Web scraping SHL catalog.
- **python-dotenv**: Manage environment variables.
- **pandas**: Data handling and evaluation.

---

## ✅ Step-by-Step Approach
### 1. Data Ingestion (Scraping)
- Crawl SHL catalog pages.
- Extract fields: `name`, `url`, `type (K/P)`, `duration`, `tags`, `description`.
- Store in SQLite DB and JSON backup.

### 2. Embedding & Indexing
- Generate embeddings for each item using HuggingFace or Groq models.
- Store vectors in FAISS index with metadata.

### 3. Retrieval
- Implement **hybrid retrieval**:
  - BM25 for keyword matching.
  - FAISS for semantic similarity.
- Merge results and keep top-N candidates.

### 4. Reranking & Filtering
- Apply hard filters:
  - Duration ≤ requested.
  - Exclude pre-packaged job solutions.
- Use cross-encoder reranker for semantic scoring.
- Enforce **K/P balance** for mixed queries.

### 5. LLM Orchestration
- Parse query for constraints (skills, duration, type).
- Format final recommendations (5–10 items).

### 6. API Endpoints
- `/health` → Check API status.
- `/recommend` → Input: `{query_text: "...", top_k: 10}` → Output: JSON list of `{name, url}`.

### 7. Frontend
- Streamlit app with text input for query/JD.
- Display recommended assessments in a table.

### 8. Evaluation
- Compute **Mean Recall@10** using Train-Set.
- Iterate on embeddings, retrieval weights, and reranker prompts.

---

## 🚀 Deployment Notes
- **API**: Deploy FastAPI on Render, Vercel, or Azure.
- **Frontend**: Deploy Streamlit on Streamlit Cloud or Render.
- Use `.env` for API keys and configs.

---

## ▶️ How to Run
```bash
# Clone repo
git clone <repo-url>
cd shl-intelligent-recommendation

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env .env

# Run scraper
python scraping/shl_scraper.py

# Build index
python indexing/build_index.py

# Start API
uvicorn api.main:app --reload

# Start Streamlit UI
streamlit run app/ui.py
```

---

## 📊 Evaluation Metric
**Mean Recall@10**:
\[ Recall@K = (Relevant items in top K) / (Total relevant items) \]

---

