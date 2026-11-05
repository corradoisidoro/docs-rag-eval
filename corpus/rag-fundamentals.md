# RAG Fundamentals

## Retrieval-Augmented Generation (RAG)

Retrieval-Augmented Generation (RAG) is an architecture
that combines information retrieval with language generation.

A RAG system retrieves relevant information from an external
knowledge source before asking a language model to generate
an answer.

RAG helps language models answer questions using private,
domain-specific, or frequently updated information.

A basic RAG pipeline consists of two main stages:

1. Indexing: documents are loaded, split into chunks,
   converted into embeddings, and stored.
2. Retrieval and generation: a question is converted into
   an embedding, relevant chunks are retrieved, and their
   content is passed to a language model.

RAG does not require retraining the language model when
the knowledge base changes.

## Text Embeddings

An embedding is a numerical representation of text.

An embedding model converts text into a vector of numbers.
Texts with similar meanings should have similar vector
representations.

For example, the sentences "How does RAG work?" and
"Explain retrieval augmented generation" have similar
meanings and should have relatively similar embeddings.

Embeddings allow a system to search by semantic meaning
rather than relying only on exact keyword matches.

In a RAG system, each document chunk is converted into
an embedding during ingestion.

The user's question is also converted into an embedding
during retrieval.

The system compares the question embedding with stored
document embeddings to find relevant chunks.

Cosine similarity is one common method for measuring
similarity between two embedding vectors.

## Document Retrieval

Document retrieval is the process of finding relevant
information from a collection of indexed documents.

In a vector-based retrieval system, documents are divided
into smaller chunks.

Each chunk is converted into an embedding and stored
in a vector store.

When a user asks a question, the question is converted
into an embedding.

The retrieval system compares the question embedding
with stored chunk embeddings.

The top-k parameter controls how many of the most relevant
chunks are returned.

For example, if top-k is 3, the system returns the three
chunks with the highest similarity scores.

The retrieved chunks are then provided as context to
the language model.
