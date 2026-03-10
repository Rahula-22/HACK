"""
Quick script to process all PDFs in the data/pdfs folder
Run this to create the vectorstore without starting the web interface
"""

from document_processor import DocumentProcessor
from models import VectorDatabase
import config

def main():
    print("=" * 50)
    print("Processing PDF Documents")
    print("=" * 50)
    
    # Initialize processor and database
    processor = DocumentProcessor(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP
    )
    vector_db = VectorDatabase(config.VECTORSTORE_DIRECTORY)
    
    # Process all PDFs in the directory
    print(f"\nLooking for PDFs in: {config.PDF_DIRECTORY}")
    chunks = processor.process_directory(config.PDF_DIRECTORY)
    
    if not chunks:
        print("\n❌ No PDF files found or no content extracted!")
        print(f"Please add PDF files to: {config.PDF_DIRECTORY}")
        return
    
    # Create vectorstore
    print(f"\nCreating vectorstore with {len(chunks)} chunks...")
    vector_db.create_vectorstore(chunks)
    
    print("\n" + "=" * 50)
    print("✅ Processing complete!")
    print("=" * 50)
    print(f"Total chunks processed: {len(chunks)}")
    print(f"Vectorstore saved to: {config.VECTORSTORE_DIRECTORY}")
    print("\nYou can now run 'streamlit run app.py' to start chatting!")

if __name__ == "__main__":
    main()
