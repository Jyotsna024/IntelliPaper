# 📄 IntelliPaper

**IntelliPaper** is an AI-powered research paper assistant that helps students and researchers understand academic papers quickly. Upload a research paper (PDF) or paste academic text, and the application generates a complete study pack including summaries, simplified explanations, architecture flow, exam-oriented questions, and interactive Q&A.

---

## 🚀 Features

- Generate concise AI-powered summaries of research papers.
- Explain complex concepts in simple language (ELI5).
- Extract key contributions and methodology.
- Generate architecture/workflow diagrams in text format.
- Create exam-oriented questions and answers.
- Calculate reading time and readability score.
- Ask questions about the uploaded paper using AI.
- Upload PDF files or paste research text directly.

---

## 🛠 Tech Stack

**Backend**
- Python
- Flask
- Flask-CORS

**AI & NLP**
- Google Gemini API
- spaCy

**PDF Processing**
- PyMuPDF (fitz)
- pdfminer.six

**Other Libraries**
- python-dotenv
- logging

---

## 📂 Project Structure

```text
IntelliPaper/
│
├── app.py
├── requirements.txt
├── README.md
├── .env.example
│
├── templates/
│   └── index.html
│
├── static/
│   ├── css/
│   ├── js/
│   └── images/
│
├── uploads/
│
└── utils/
```

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/Jyotsna024/IntelliPaper.git
cd IntelliPaper
```

### 2. Create a virtual environment (Recommended)

**Windows**

```bash
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Download the spaCy model

```bash
python -m spacy download en_core_web_sm
```

### 5. Configure the API key

Create a `.env` file in the project root.

```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

### 6. Run the application

```bash
python app.py
```

Open your browser and visit:

```
http://127.0.0.1:5000
```

---

## 🔄 Workflow

```text
          Upload PDF / Paste Text
                     │
                     ▼
          Extract Text from Document
                     │
                     ▼
           NLP Preprocessing
                     │
                     ▼
           Google Gemini API
                     │
     ┌───────────────┼────────────────┐
     ▼               ▼                ▼
 Summary       Simple Explanation   Architecture Flow
                     │
                     ▼
      Exam Q&A • Reading Analysis • Paper Chat
```

---

## 📸 Screenshots

### Home Page

Add your homepage screenshot here.

```
screenshots/home.png
```

### Generated Study Pack

Add the generated results screenshot here.

```
screenshots/result.png
```

---

## 🎯 Future Improvements

- OCR support for scanned PDFs
- Multi-language support
- Citation extraction
- Compare multiple research papers
- Export study pack as PDF
- Dark mode
- RAG-based document chat
- Semantic search across papers

---

## 🤝 Contributing

Contributions are welcome.

1. Fork the repository
2. Create a new branch

```bash
git checkout -b feature-name
```

3. Commit your changes

```bash
git commit -m "Add new feature"
```

4. Push to your branch

```bash
git push origin feature-name
```

5. Open a Pull Request

---

## 👩‍💻 Author

**G Jyotsna**

B.Tech – Computer Science & Engineering (AI/ML)  
Alliance University, Bengaluru

GitHub: https://github.com/Jyotsna024

---

## ⭐ Support

If you found this project useful, consider giving it a ⭐ on GitHub.

---

## 📄 License

This project is licensed under the MIT License.
