# AI-Powered Hybrid Fraud Detection System

A modern, containerized Fraud Detection platform that combines a deterministic **Rule-Based Engine** with an advanced **Machine Learning (XGBoost) Model** to detect both obvious and evasive financial fraud in real-time.

---

## Key Features

* **Hybrid Scoring Engine**: Evaluates transactions using hard-coded business rules alongside behavioral ML models, dramatically reducing false positives and catching evasive fraud that rules miss.
* **Live Case Management Dashboard**: A professional, multi-page Streamlit UI for investigators to monitor live traffic, review customer history, and manage the alert queue (Approve/Block/Claim).
* **Automated Customer Communication**: Integrated SMTP email service that automatically dispatches verification requests to customers for suspicious transactions.
* **Fully Containerized**: The entire stack (API, Frontend, Database) is orchestrated via Docker Compose for one-click deployment.
* **Simulation & Testing Scripts**: Built-in Python scripts to generate realistic transaction data, simulate fraud rings, and benchmark ML performance against the rule engine.

---

##  Tech Stack

* **Backend API**: FastAPI (Python)
* **Frontend UI**: Streamlit
* **Database**: PostgreSQL
* **Machine Learning**: XGBoost, Scikit-Learn, Pandas
* **Deployment**: Docker & Docker Compose

---

## Project Structure

```text
├── app/                  # FastAPI backend application & DB models
├── UI/                   # Streamlit dashboard pages & email service
├── ml_features/          # Real-time feature engineering (SQL & Python)
├── model_training/       # Jupyter notebooks for training the XGBoost model
├── rules/                # JSON-based Rule Engine configuration
├── scripts/              # Data generation, fraud injection, and benchmarking scripts
├── test_data/            # Mock datasets for training and testing
└── docker-compose.yml    # Docker orchestration file
```

---

## Getting Started (How to Run)

### 1. Prerequisites
* **Docker Desktop** installed and running.
* **Python 3.9+** (if you wish to run the testing scripts locally).

### 2. Boot up the Platform
Simply run the following command in the root directory to build the images and start the database, API, and UI containers:
```bash
docker-compose up -d --build
```

### 3. Access the Services
* **Investigator Dashboard (Streamlit)**: `http://localhost:8501`
* **API Documentation (Swagger UI)**: `http://localhost:8000/docs`
---

##  Testing with Postman

To test the live system, a fully configured Postman collection is included in the project root: `Fraud_Detection_API.postman_collection.json`.

**1. Import the Collection**
* Open Postman.
* Click **Import** and select the `Fraud_Detection_API.postman_collection.json` file from the repository.

**2. Send Test Transactions**
* Select the **Score Transaction** (`POST /score`) endpoint.
* Send a JSON payload containing transaction details like `amount`, `txn_type` (e.g., `"UPI"` or `"Credit Card"`), and `customer_id`.
* The Hybrid Engine will instantly analyze the payload, run the XGBoost model, evaluate the Rule Engine, and return a risk assessment (`ALLOW`, `REVIEW`, or `BLOCK`).

**3. Watch it Live on the Dashboard!**
Once you send a suspicious transaction from Postman, switch over to your Streamlit Live Dashboard (`http://localhost:8501`). You will instantly see the transaction appear in the live feed. If the API flagged it as `REVIEW` or `BLOCK`, it will automatically generate an investigation ticket in the **Case Management** tab!

---

##  Documentation
For detailed performance metrics and architectural decisions, please refer to:
* `rules_vs_ml_comparison.md`: Empirical comparison of both engines.
* `model_performance.md`: Accuracy, Precision, and Recall metrics of the deployed XGBoost model.


---

## ?? Future Enhancements
* **Generative AI Explainability (XAI)**: Integration of a lightweight Local LLM to dynamically translate the XGBoost SHAP impact values into highly contextual, natural-language narratives for fraud investigators.
* **Graph Database Integration**: Implementing a Graph layer (e.g., Neo4j) to map out complex fraud rings and device-sharing networks across multiple accounts.
