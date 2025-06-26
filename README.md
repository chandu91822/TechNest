# 📄 Technest — Resume Analyzer

**Technest** is an intelligent resume analyzer built using AWS Serverless technologies. It processes uploaded resumes to evaluate and score them, suggest improvements, and recommend matching jobs — all delivered straight to your email!

---

## 🧠 Features

- 📑 Upload resumes in PDF/Image formats
- 🧮 Smart resume scoring with actionable tips
- 🧠 Extracted skills from resume matched with trending tech stack
- 🔍 Real-time job and internship suggestions via RapidAPI
- 📬 Personalized feedback delivered via email
- ☁️ Fully serverless — scalable and efficient using AWS Lambda

---

## 🚀 Powered By AWS

This project is built on top of modern AWS cloud services:

| Service        | Role                                                         |
|----------------|--------------------------------------------------------------|
| **S3**         | Store uploaded resumes                                       |
| **Textract**   | Extract text from uploaded PDF/image resumes                 |
| **Lambda**     | Process resumes and run scoring logic serverlessly           |
| **API Gateway**| Expose a public HTTPS endpoint to invoke Lambda              |
| **SES**        | Send personalized email with score and job suggestions       |

---

## 🛠️ Tech Stack

- 🧑‍💻 **Backend**: Python 3 (AWS Lambda)
- 🌐 **Frontend**: HTML, CSS, JavaScript
- 📡 **API Integration**: [RapidAPI – JSearch](https://rapidapi.com/)
- 📨 **Email Service**: Amazon Simple Email Service (SES)

---

## 📁 Project Structure

technest-resume-analyzer/
├── index.html # UI homepage for file upload
├── style.css # Clean and modern CSS for front-end
├── script.js # JS logic for form and feedback
├── lambda_function.py # Core Lambda backend logic
├── README.md # Project documentation (this file)
