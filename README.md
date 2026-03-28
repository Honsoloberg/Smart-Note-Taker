# Smart-Note-Taker

## Description
The objective of this project is to replace the traditional student notetaker. At Ontario Tech, the student accessibility services (SAS) center provides notetakers for students who need assistance taking notes for their lectures. However, there are several problems associated with the traditional human notetakers. A notetaker is a volunteer position with little to no compensation, and it can be difficult for the SAS center to recruit for the job. The person hired to take notes is subject to human error, may not be enrolled in the course, and may miss important information. They may not properly understand the material, or they may get distracted, sick, or miss some crucial point that the professor was trying to make. Furthermore, after the lecture, they may take several hours to finish writing and formatting the notes, which delays delivery and reduces efficiency for both the student taking the notes and the student relying on them. 

A proposed solution for this problem should ideally eliminate the general inefficiencies of the human notetaker. The solution should be readily available to solve the issue of recruitment for the SAS center. It should be able to capture everything to eliminate human error. Finally, it should increase efficiency by completing the notes faster and more accurately than a human notetaker. The notes produced for the student using this solution should capture everything said during the lecture and be properly formatted in a manner that is easy to understand. 

After identifying the problem scope, the goal of this project is to build an AI-powered Smart Notetaker. This device will allow students to record lectures and produce notes based on a transcription of the recorded audio. The end product will include a hardware component for recording the lecture audio, and an app that connects to the hardware. The app will allow the student to download recorded lectures, transcribe the lectures into notes, and send questions to an AI based on the content. The addition of an interactive AI component can alleviate the disconnect between the notetaker and student, as the student can interact with an AI for better explanations after the notes are produced. The student will be able to talk with the AI, generate sample questions, reword sections, and clarify what the speaker meant. By keeping the majority of the UI on the app, the navigation of the product will be more intuitive for users. By keeping the recording component separate, services like the SAS center have control over which parties are authorized to use the Notetaker. 


## Developers
- Logan Butler
- Eric Deleenheer
- Rhea Mathias
- Rivka Sagi 

## Requirements
- Hardware component for recording lectures, should be used by the student
    - Student gains access to hardware device from SAS center
    - Student brings device to professor to record during lecture
- Student has a working app that can connect to the hardware device
- AI should convert captured lecture to accurate, well structured notes and summarization using NLP
- Enable the following features:
    - Topic-based organization
    - Generate practice questions
    - Ask specific questions to AI
- Identify different speakers
- Ensure accessibility and comply with data privacy regulations