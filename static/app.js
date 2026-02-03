document.addEventListener("DOMContentLoaded", () => {
  // --- Prevent Horizontal Scrolling ---
  let lastScrollTop = 0;
  let ticking = false;

  function preventHorizontalScroll() {
    if (window.innerWidth !== document.documentElement.clientWidth) {
      document.body.style.overflowX = 'hidden';
      document.documentElement.style.overflowX = 'hidden';
    }
  }

  window.addEventListener('resize', preventHorizontalScroll);
  preventHorizontalScroll();

  // --- Navbar Scroll Effect ---
  const navbar = document.querySelector('.navbar');
  let lastScroll = 0;

  function handleNavbarScroll() {
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    
    if (scrollTop > 50) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
    
    lastScroll = scrollTop;
    ticking = false;
  }

  window.addEventListener('scroll', () => {
    if (!ticking) {
      window.requestAnimationFrame(handleNavbarScroll);
      ticking = true;
    }
  });

  // --- Navbar Toggle Functionality ---
  const navbarToggle = document.getElementById("navbarToggle");
  const navbarMenu = document.getElementById("navbarMenu");

  if (navbarToggle && navbarMenu) {
    navbarToggle.addEventListener("click", (e) => {
      e.stopPropagation();
      navbarMenu.classList.toggle("active");
      navbarToggle.classList.toggle("active");
      
      // Prevent body scroll when menu is open
      if (navbarMenu.classList.contains("active")) {
        document.body.style.overflow = 'hidden';
      } else {
        document.body.style.overflow = '';
      }
    });

    // Close menu when clicking outside
    document.addEventListener("click", (e) => {
      if (!navbarToggle.contains(e.target) && !navbarMenu.contains(e.target)) {
        navbarMenu.classList.remove("active");
        navbarToggle.classList.remove("active");
        document.body.style.overflow = '';
      }
    });

    // Close menu when clicking on a link
    const navbarLinks = navbarMenu.querySelectorAll("a");
    navbarLinks.forEach((link) => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        navbarMenu.classList.remove("active");
        navbarToggle.classList.remove("active");
        document.body.style.overflow = '';
        
        // Smooth scroll to section if anchor exists
        const targetId = link.getAttribute('href');
        if (targetId && targetId.startsWith('#')) {
          const targetElement = document.querySelector(targetId);
          if (targetElement) {
            const offsetTop = targetElement.offsetTop - 70;
            window.scrollTo({
              top: offsetTop,
              behavior: 'smooth'
            });
          }
        }
      });
    });
  }

  // --- Tab Management ---
  const fileUploadTab = document.getElementById("fileUploadTab");
  const recordAudioTab = document.getElementById("recordAudioTab");
  const uploadTabContent = document.getElementById("uploadTabContent");
  const recordTabContent = document.getElementById("recordTabContent");

  function switchTab(tabName) {
    // Remove active class from all tabs and content
    fileUploadTab.classList.remove("active");
    recordAudioTab.classList.remove("active");
    uploadTabContent.classList.remove("active");
    recordTabContent.classList.remove("active");

    // Add active class to selected tab and content
    if (tabName === "upload") {
      fileUploadTab.classList.add("active");
      uploadTabContent.classList.add("active");
    } else {
      recordAudioTab.classList.add("active");
      recordTabContent.classList.add("active");
    }
  }

  fileUploadTab.addEventListener("click", () => switchTab("upload"));
  recordAudioTab.addEventListener("click", () => switchTab("record"));

  // --- References to HTML elements for Recording States ---
  const idleState = document.getElementById("idleState");
  const recordingState = document.getElementById("recordingState");
  const previewState = document.getElementById("previewState");
  
  const startButton = document.getElementById("startButton");
  const pauseResumeButton = document.getElementById("pauseResumeButton");
  const pauseResumeIcon = document.getElementById("pauseResumeIcon");
  const pauseResumeText = document.getElementById("pauseResumeText");
  const stopButton = document.getElementById("stopButton");
  
  const recordStatus = document.getElementById("recordStatus");
  const recordingStatus = document.getElementById("recordingStatus");
  const previewStatus = document.getElementById("previewStatus");
  
  const audioPreview = document.getElementById("audioPreview");
  const deleteButton = document.getElementById("deleteButton");
  const uploadRecordButton = document.getElementById("uploadRecordButton");
  const cancelRecordButton = document.getElementById("cancelRecordButton");

  // --- References to HTML elements for Uploading ---
  const fileInput = document.getElementById("fileInput");
  const triggerFileInput = document.getElementById("triggerFileInput");
  const uploadButton = document.getElementById("uploadButton");
  const uploadStatus = document.getElementById("uploadStatus");
  const uploadZone = document.getElementById("uploadZone");
  const fileSelectedInfo = document.getElementById("fileSelectedInfo");
  const selectedFileName = document.getElementById("selectedFileName");

  let mediaRecorder;
  let audioChunks = [];
  let mediaStream;
  let currentState = 'idle'; // 'idle', 'recording', 'preview'
  let audioBlob = null;
  let audioUrl = null;
  let isPaused = false;
  let currentSessionId = null; // Track current session for cleanup

  // =======================================================
  // --- Reusable Function to Upload Any File/Blob ---
  // =======================================================
  async function uploadFileOrBlob(fileOrBlob, statusElement) {
    // 1. Create a FormData object (the "envelope")
    const formData = new FormData();

    let filename;
    // Check if it's a Blob (from live recording) or a File (from upload)
    if (fileOrBlob instanceof Blob && !(fileOrBlob instanceof File)) {
      // It's a live recording, so let's create a filename
      filename = `live_recording_${new Date().toISOString()}.webm`;
    } else {
      // It's a file from the user's computer
      filename = fileOrBlob.name;
    }

    // 2. Add the file to the envelope.
    // 'audio_file' MUST match the name in main.py
    // We also give it the filename we just decided on.
    formData.append("audio_file", fileOrBlob, filename);

    statusElement.textContent = `Uploading ${filename}...`;
    statusElement.classList.remove("error", "success");
    statusElement.classList.add("show");

    try {
      // 3. Send the envelope to the server's '/upload-audio' route
      const response = await fetch("/upload-audio", {
        method: "POST",
        body: formData,
      });

      // 4. Get the JSON response
      const result = await response.json();

      // 5. Display the server's message
      if (response.ok) {
        // Cleanup previous session if exists
        if (currentSessionId) {
          await cleanupSession(currentSessionId);
        }
        
        // Store session ID for cleanup
        currentSessionId = result.session_id;
        
        // Update status with processing steps
        statusElement.textContent = "Upload complete. Processing...";
        statusElement.classList.remove("error");
        statusElement.classList.add("show");
        
        // Show processing steps
        await showProcessingSteps(statusElement, result);
        
        // If this was a recording upload, reset after showing results
        if (currentState === 'preview') {
          setTimeout(() => {
            resetRecording();
          }, 3000);
        }
      } else {
        statusElement.textContent = `Error: ${result.error}`; // Show error
        statusElement.classList.add("error");
        statusElement.classList.remove("success");
        
        // Re-enable buttons on error
        if (currentState === 'preview') {
          uploadRecordButton.disabled = false;
          cancelRecordButton.disabled = false;
        }
      }
    } catch (err) {
      console.error("Error uploading:", err);
      statusElement.textContent = "Error: Could not connect to server.";
      statusElement.classList.add("error");
      statusElement.classList.remove("success");
      
      // Re-enable buttons on error
      if (currentState === 'preview') {
        uploadRecordButton.disabled = false;
        cancelRecordButton.disabled = false;
      }
    }
  }

  // Show processing steps and PDF download link
  async function showProcessingSteps(statusElement, result) {
    // Since processing happens synchronously on server, we can show completion immediately
    statusElement.textContent = "Processing complete! Summary ready.";
    statusElement.classList.remove("error");
    statusElement.classList.add("success");
    
    // Create or update PDF download section
    let downloadSection = document.getElementById("pdfDownloadSection");
    if (!downloadSection) {
      downloadSection = document.createElement("div");
      downloadSection.id = "pdfDownloadSection";
      downloadSection.className = "pdf-download-section";
      
      // Insert after the status element's parent container
      const container = statusElement.closest('.tab-content') || statusElement.parentElement;
      container.appendChild(downloadSection);
    }
    
    downloadSection.innerHTML = `
      <div class="pdf-download-card">
        <i class="fas fa-file-pdf pdf-icon"></i>
        <h3>Your Meeting Summary is Ready!</h3>
        <p>Download your summary as a PDF file.</p>
        <a href="/download-pdf/${result.session_id}" class="download-button" download>
          <i class="fas fa-download"></i>
          Download PDF
        </a>
      </div>
    `;
    
    // Make download section visible
    downloadSection.style.display = "block";
  }

  // Cleanup function to delete files when user navigates away
  async function cleanupSession(sessionId) {
    if (!sessionId) return;
    
    try {
      const response = await fetch(`/cleanup/${sessionId}`, {
        method: "DELETE",
      });
      
      const result = await response.json();
      console.log("Cleanup result:", result);
    } catch (err) {
      console.error("Error during cleanup:", err);
    }
  }

  // Cleanup on page unload
  window.addEventListener("beforeunload", (e) => {
    if (currentSessionId) {
      // Use sendBeacon for reliable cleanup on page unload (POST method)
      navigator.sendBeacon(`/cleanup/${currentSessionId}`);
    }
  });

  // Also cleanup on visibility change (when tab becomes hidden)
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && currentSessionId) {
      cleanupSession(currentSessionId);
    }
  });

  // ===========================================
  // --- PART 1: THREE-STATE RECORDING LOGIC ---
  // ===========================================

  // State Management Functions
  function switchToState(state) {
    // Hide all states
    idleState.classList.remove("active");
    recordingState.classList.remove("active");
    previewState.classList.remove("active");
    
    // Show selected state
    if (state === 'idle') {
      idleState.classList.add("active");
      currentState = 'idle';
    } else if (state === 'recording') {
      recordingState.classList.add("active");
      currentState = 'recording';
      isPaused = false;
      updatePauseResumeButton();
    } else if (state === 'preview') {
      previewState.classList.add("active");
      currentState = 'preview';
    }
  }

  function resetRecording() {
    // Clean up media stream
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
    }
    
    // Revoke audio URL to free memory
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      audioUrl = null;
    }
    
    // Reset variables
    audioBlob = null;
    audioChunks = [];
    mediaRecorder = null;
    isPaused = false;
    
    // Reset UI
    switchToState('idle');
    recordStatus.textContent = "Status: Ready";
    recordStatus.classList.remove("recording", "error", "success");
    previewStatus.textContent = "";
    previewStatus.classList.remove("show", "error", "success");
  }

  function updatePauseResumeButton() {
    if (isPaused) {
      pauseResumeIcon.className = "fas fa-play";
      pauseResumeText.textContent = "Resume";
      pauseResumeButton.classList.add("resume");
      pauseResumeButton.classList.remove("pause");
    } else {
      pauseResumeIcon.className = "fas fa-pause";
      pauseResumeText.textContent = "Pause";
      pauseResumeButton.classList.add("pause");
      pauseResumeButton.classList.remove("resume");
    }
  }

  // Idle State: Start Recording
  startButton.addEventListener("click", async () => {
    try {
      // Request microphone access
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(mediaStream);
      audioChunks = [];
      isPaused = false;

      // Collect audio data chunks
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      // Handle recording stop
      mediaRecorder.onstop = () => {
        // Create audio blob from chunks
        audioBlob = new Blob(audioChunks, { type: "audio/webm" });
        audioUrl = URL.createObjectURL(audioBlob);
        
        // Set audio preview source
        audioPreview.src = audioUrl;
        
        // Switch to preview state
        switchToState('preview');
        previewStatus.textContent = "Review your recording before uploading.";
        previewStatus.classList.add("show");
        
        // Stop all tracks
        if (mediaStream) {
          mediaStream.getTracks().forEach((track) => track.stop());
        }
      };

      // Handle pause event
      mediaRecorder.onpause = () => {
        isPaused = true;
        updatePauseResumeButton();
        recordingStatus.textContent = "Status: Paused";
      };

      // Handle resume event
      mediaRecorder.onresume = () => {
        isPaused = false;
        updatePauseResumeButton();
        recordingStatus.textContent = "Status: Recording...";
      };

      // Start recording
      mediaRecorder.start(1000); // Collect data every second
      
      // Switch to recording state
      switchToState('recording');
      recordingStatus.textContent = "Status: Recording...";
      recordingStatus.classList.add("recording");
      
    } catch (err) {
      console.error("Error accessing microphone:", err);
      recordStatus.textContent = "Error: Could not access microphone.";
      recordStatus.classList.add("error");
      resetRecording();
    }
  });

  // Recording State: Pause/Resume Toggle
  pauseResumeButton.addEventListener("click", () => {
    if (!mediaRecorder || currentState !== 'recording') return;

    try {
      if (mediaRecorder.state === "recording") {
        mediaRecorder.pause();
      } else if (mediaRecorder.state === "paused") {
        mediaRecorder.resume();
      }
    } catch (err) {
      console.error("Error pausing/resuming:", err);
      recordingStatus.textContent = "Error: Could not pause/resume recording.";
      recordingStatus.classList.add("error");
    }
  });

  // Recording State: Stop Recording
  stopButton.addEventListener("click", () => {
    if (!mediaRecorder || currentState !== 'recording') return;

    try {
      if (mediaRecorder.state === "recording" || mediaRecorder.state === "paused") {
        mediaRecorder.stop();
      }
    } catch (err) {
      console.error("Error stopping recording:", err);
      recordingStatus.textContent = "Error: Could not stop recording.";
      recordingStatus.classList.add("error");
    }
  });

  // Preview State: Delete/Cancel Button
  function handleCancel() {
    resetRecording();
  }

  deleteButton.addEventListener("click", handleCancel);
  cancelRecordButton.addEventListener("click", handleCancel);

  // Preview State: Upload Button
  uploadRecordButton.addEventListener("click", () => {
    if (!audioBlob || currentState !== 'preview') return;

    // Upload the blob to the server
    uploadFileOrBlob(audioBlob, previewStatus);
    
    // Update UI
    previewStatus.textContent = "Uploading...";
    previewStatus.classList.add("show");
    previewStatus.classList.remove("error");
    
    // Disable buttons during upload
    uploadRecordButton.disabled = true;
    cancelRecordButton.disabled = true;
    
    // After upload completes, reset (handled in uploadFileOrBlob callback)
  });

  // ===========================================
  // --- PART 2: FILE UPLOAD LOGIC ---
  // ===========================================

  // Trigger file input when upload button is clicked
  triggerFileInput.addEventListener("click", () => {
    fileInput.click();
  });

  // Handle file selection
  fileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
      selectedFileName.textContent = `Selected: ${file.name}`;
      fileSelectedInfo.classList.add("show");
      uploadStatus.textContent = "";
      uploadStatus.classList.remove("show", "error");
    }
  });

  // Upload button click handler
  uploadButton.addEventListener("click", () => {
    const file = fileInput.files[0];
    if (!file) {
      uploadStatus.textContent = "Please select a file first.";
      uploadStatus.classList.add("error", "show");
      return;
    }

    // Use the reusable upload function
    uploadFileOrBlob(file, uploadStatus);
  });

  // ===========================================
  // --- Drag and Drop Functionality ---
  // ===========================================
  
  uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZone.classList.add("dragover");
  });

  uploadZone.addEventListener("dragleave", () => {
    uploadZone.classList.remove("dragover");
  });

  uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.classList.remove("dragover");
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      // Check if it's an audio, video, or PDF file
      const fileName = file.name.toLowerCase();
      const isAudio = file.type.startsWith("audio/");
      const isVideo = file.type.startsWith("video/");
      const isPdf = file.type === "application/pdf" || fileName.endsWith(".pdf");
      
      if (isAudio || isVideo || isPdf) {
        // Set the file input
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        fileInput.files = dataTransfer.files;
        
        // Trigger change event
        const event = new Event("change", { bubbles: true });
        fileInput.dispatchEvent(event);
      } else {
        uploadStatus.textContent = "Please select an audio, video, or PDF file.";
        uploadStatus.classList.add("error", "show");
      }
    }
  });

  // Click on upload zone to trigger file input
  uploadZone.addEventListener("click", (e) => {
    // Only trigger if not clicking the button itself
    if (e.target === uploadZone || e.target.closest(".upload-zone-text") || e.target.closest(".upload-icon")) {
      fileInput.click();
    }
  });
});
