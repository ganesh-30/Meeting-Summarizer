import os
import uuid
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from transcribe import transcribe_audio_file
from pdf_extractor import extract_text_from_pdf
from summary_generator import generate_summary
from pdf_generator import generate_pdf

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
TRANSCRIPT_FOLDER = os.path.join('data', 'transcripts')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['TRANSCRIPT_FOLDER'] = TRANSCRIPT_FOLDER

for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, TRANSCRIPT_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

session_files = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload-audio', methods=['POST'])
def upload_audio_file():
    if 'audio_file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['audio_file']
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if file:

        session_id = str(uuid.uuid4())
        original_filename = secure_filename(file.filename)
        filename_base, ext = os.path.splitext(original_filename)
        ext_lower = ext.lower()
        
        is_pdf = ext_lower == '.pdf'
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.3gp']
        audio_extensions = ['.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg', '.wma']
        is_video = ext_lower in video_extensions
        is_audio = ext_lower in audio_extensions
        
        unique_filename = f"{session_id}_{filename_base}{ext}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        transcript_path = None
        pdf_path = None

        try:
         
            if os.path.exists(save_path):
                os.remove(save_path)

            
            file.save(save_path)

            if is_pdf:
 
                print(f"Processing PDF transcript file: {save_path}")
                transcript_path = extract_text_from_pdf(save_path)
                if not transcript_path:
                    raise RuntimeError("Failed to extract text from PDF file")
            elif is_audio or is_video:
           
                file_type = "video" if is_video else "audio"
                print(f"Processing {file_type} file: {save_path}")
                transcript_path = transcribe_audio_file(save_path)
                if not transcript_path:
                    raise RuntimeError(f"Failed to transcribe {file_type} file")
            else:
                raise RuntimeError(f"Unsupported file type: {ext}. Please upload audio, video, or PDF files.")

            summary_text = generate_summary(transcript_path)
            if not summary_text:
                raise RuntimeError("Failed to generate summary")

            pdf_filename = f"{filename_base}_{session_id}_summary.pdf"
            pdf_path = os.path.join(app.config['OUTPUT_FOLDER'], pdf_filename)
            pdf_result = generate_pdf(summary_text, pdf_path, title="Meeting Summary")
            if not pdf_result:
                raise RuntimeError("Failed to generate PDF")

            session_files[session_id] = {
                'uploaded_file': save_path, 
                'transcript_file': transcript_path,
                'pdf_file': pdf_path,
                'session_id': session_id,
                'file_type': 'pdf' if is_pdf else ('video' if is_video else 'audio')
            }

            return jsonify({
                "message": "File processed successfully",
                "session_id": session_id,
                "pdf_filename": os.path.basename(pdf_path),
                "status": "completed"
            }), 200

        except Exception as e:
          
            try:
                if save_path and os.path.exists(save_path):
                    os.remove(save_path)
            except Exception:
                pass
            try:
                if transcript_path and os.path.exists(transcript_path):
                    os.remove(transcript_path)
            except Exception:
                pass
            try:
                if pdf_path and os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except Exception:
                pass

            return jsonify({"error": f"Failed to process file: {str(e)}"}), 500

@app.route('/download-pdf/<session_id>', methods=['GET'])
def download_pdf(session_id):
    try:
        if session_id not in session_files:
            return jsonify({"error": "Session not found"}), 404
        
        pdf_path = session_files[session_id]['pdf_file']
        
        if not os.path.exists(pdf_path):
            return jsonify({"error": "PDF file not found"}), 404
        
        pdf_filename = os.path.basename(pdf_path)
        return send_file(pdf_path, as_attachment=True, download_name=pdf_filename)
    
    except Exception as e:
        return jsonify({"error": f"Failed to download PDF: {str(e)}"}), 500

@app.route('/cleanup/<session_id>', methods=['DELETE', 'POST'])
def cleanup_session(session_id):
    try:
        if session_id not in session_files:
            return jsonify({"error": "Session not found"}), 404
        
        files_to_delete = session_files[session_id]
        deleted_files = []
        errors = []
        
        if 'uploaded_file' in files_to_delete and os.path.exists(files_to_delete['uploaded_file']):
            try:
                os.remove(files_to_delete['uploaded_file'])
                deleted_files.append(files_to_delete['uploaded_file'])
            except Exception as e:
                errors.append(f"Failed to delete uploaded file: {str(e)}")
        
        if 'audio_file' in files_to_delete and os.path.exists(files_to_delete['audio_file']):
            try:
                os.remove(files_to_delete['audio_file'])
                deleted_files.append(files_to_delete['audio_file'])
            except Exception as e:
                errors.append(f"Failed to delete audio file: {str(e)}")
        
        if 'transcript_file' in files_to_delete and os.path.exists(files_to_delete['transcript_file']):
            try:
                os.remove(files_to_delete['transcript_file'])
                deleted_files.append(files_to_delete['transcript_file'])
            except Exception as e:
                errors.append(f"Failed to delete transcript file: {str(e)}")
        
        if 'pdf_file' in files_to_delete and os.path.exists(files_to_delete['pdf_file']):
            try:
                os.remove(files_to_delete['pdf_file'])
                deleted_files.append(files_to_delete['pdf_file'])
            except Exception as e:
                errors.append(f"Failed to delete PDF file: {str(e)}")
        
        del session_files[session_id]
        
        return jsonify({
            "message": "Files cleaned up",
            "deleted_files": deleted_files,
            "errors": errors if errors else None
        }), 200
    
    except Exception as e:
        return jsonify({"error": f"Failed to cleanup files: {str(e)}"}), 500

@app.route('/status/<session_id>', methods=['GET'])
def get_status(session_id):
    if session_id in session_files:
        return jsonify({
            "status": "completed",
            "session_id": session_id,
            "pdf_filename": os.path.basename(session_files[session_id]['pdf_file'])
        }), 200
    else:
        return jsonify({"error": "Session not found"}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)