import json
import os
from typing import Dict, List, Any, Optional

import requests
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from dotenv import load_dotenv

class ContosoSearchPlugin:
    def __init__(self):
        load_dotenv()
       
        self.openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.embedding_deployment = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT_NAME")
        self.embedding_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2023-05-15")
        # Get embedding endpoint from environment variable
        self.embedding_endpoint = os.getenv("AZURE_OPENAI_EMBED_ENDPOINT", self.openai_endpoint)
       
        self.search_endpoint = os.getenv("AI_SEARCH_URL")
        self.search_key = os.getenv("AI_SEARCH_KEY")
        self.search_index_name = os.getenv("AZURE_SEARCH_INDEX", "employeehandbook")
       
        self.search_client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=self.search_index_name,
            credential=AzureKeyCredential(self.search_key)
        )
        
        # Chat completion endpoint for rephrasing
        self.chat_endpoint = self.openai_endpoint
        self.chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
        self.chat_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2023-12-01-preview")
       
    def generate_embedding(self, text: str) -> List[float]:
        if not text:
            raise ValueError("Input text cannot be empty")
           
        url = f"{self.embedding_endpoint}/openai/deployments/{self.embedding_deployment}/embeddings?api-version={self.embedding_api_version}"
        headers = {
            "Content-Type": "application/json",
            "api-key": self.openai_api_key
        }
        payload = {
            "input": text
            # Remove dimensions parameter as it's not supported by this model
        }
       
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            embedding_data = response.json()
            return embedding_data["data"][0]["embedding"]
        except Exception as e:
            raise Exception(f"Failed to generate embedding: {str(e)}")
    
    def rephrase_with_chat_model(self, content: str, query: str) -> str:
        """
        Use the chat model to rephrase and improve the content from search results
        """
        try:
            url = f"{self.chat_endpoint}/openai/deployments/{self.chat_deployment}/chat/completions?api-version={self.chat_api_version}"
            
            headers = {
                "Content-Type": "application/json",
                "api-key": self.openai_api_key
            }
            
            # Create a prompt to rephrase the content
            system_prompt = """You are a helpful assistant that rephrases and improves content from an employee handbook. 
            Your task is to:
            1. Make the content clear and easy to understand
            2. Keep all important information intact
            3. Structure the response in a professional manner
            4. Focus on answering the specific question asked
            5. Remove any redundant or unclear text
            6. Provide a direct, specific answer to the question"""
            
            user_prompt = f"""Please rephrase and improve the following content from Contoso's employee handbook to directly answer this specific question: "{query}"

Content from handbook:
{content}

Please provide a clear, professional, and direct response that specifically answers the question. Do not include generic information that doesn't address the question."""

            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0.2,  # Lower temperature for more consistent responses
                "top_p": 0.9
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            rephrased_content = result["choices"][0]["message"]["content"]
            
            return rephrased_content.strip()
            
        except Exception as e:
            # If rephrasing fails, return the original content
            return content
   
    def search_documents(self, query: str, top: int = 3) -> List[Dict[str, Any]]:
        try:
            # Generate embedding for the query
            query_embedding = self.generate_embedding(query)
           
            # Create a vectorized query
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=top,
                fields="contentVector"
            )
           
            # Enhance search with filters for better relevance
            search_filter = None
            query_lower = query.lower()
            
            # Add search filters based on query type for better targeting
            if 'security' in query_lower or 'data' in query_lower:
                search_filter = "search.ismatch('security OR data OR confidential OR privacy', 'content')"
            elif 'vacation' in query_lower or 'pto' in query_lower:
                search_filter = "search.ismatch('vacation OR pto OR leave OR time off', 'content')"
            elif 'policy' in query_lower:
                search_filter = "search.ismatch('policy OR guideline OR procedure', 'content')"
           
            # Execute the search
            results = self.search_client.search(
                search_text=query,  # Also include text search for hybrid retrieval
                vector_queries=[vector_query],
                select="*",  # Select all fields
                filter=search_filter,
                top=top
            )
           
            # Format the results
            search_results = []
            for result in results:
                result_dict = {
                    "score": result["@search.score"]
                }
                
                # Add all other fields that exist
                for field in ["chunk_id", "content", "title", "url", "filepath", "parent_id"]:
                    if field in result:
                        result_dict[field] = result[field]
                
                search_results.append(result_dict)
           
            return search_results
           
        except Exception as e:
            # If filtered search fails, try without filter
            try:
                results = self.search_client.search(
                    search_text=query,
                    vector_queries=[vector_query],
                    select="*",
                    top=top
                )
                
                search_results = []
                for result in results:
                    result_dict = {
                        "score": result["@search.score"]
                    }
                    
                    for field in ["chunk_id", "content", "title", "url", "filepath", "parent_id"]:
                        if field in result:
                            result_dict[field] = result[field]
                    
                    search_results.append(result_dict)
                
                return search_results
            except Exception as e2:
                raise Exception(f"Search failed: {str(e2)}")
   
    def query_handbook(self, query: str, top: int = 3) -> str:
        try:
            results = self.search_documents(query, top)
           
            # Format the results into a nice response
            if not results:
                return "No relevant information found in the Contoso Handbook."
           
            # Analyze the query to provide more specific responses
            query_lower = query.lower()
            
            # Check if it's a specific policy question
            if any(keyword in query_lower for keyword in ['data security', 'security policy', 'information security']):
                response = f"**Contoso Data Security Policy Information:**\n\n"
            elif any(keyword in query_lower for keyword in ['vacation', 'pto', 'time off', 'leave']):
                response = f"**Contoso Vacation and Time Off Policy:**\n\n"
            elif any(keyword in query_lower for keyword in ['confidential', 'confidentiality']):
                response = f"**Contoso Confidentiality Guidelines:**\n\n"
            elif any(keyword in query_lower for keyword in ['remote work', 'work from home', 'telework']):
                response = f"**Contoso Remote Work Policy:**\n\n"
            elif any(keyword in query_lower for keyword in ['benefits', 'health', 'insurance']):
                response = f"**Contoso Employee Benefits:**\n\n"
            else:
                response = f"**Information from Contoso Employee Handbook regarding '{query}':**\n\n"
            
            # Process each result for more specific information
            all_content = []
            for i, result in enumerate(results, 1):
                content = result.get('content', 'No content available')
                
                # Extract key information based on query type
                if 'data security' in query_lower or 'security policy' in query_lower:
                    # Look for specific security-related information
                    security_keywords = ['password', 'encryption', 'access', 'confidential', 'protect', 'secure', 'data handling', 'classification']
                    relevant_sentences = self.extract_relevant_sentences(content, security_keywords)
                    if relevant_sentences:
                        content = relevant_sentences
                
                elif 'vacation' in query_lower or 'pto' in query_lower:
                    # Look for vacation-specific information
                    vacation_keywords = ['days', 'hours', 'request', 'approval', 'accrual', 'balance', 'holiday']
                    relevant_sentences = self.extract_relevant_sentences(content, vacation_keywords)
                    if relevant_sentences:
                        content = relevant_sentences
                
                all_content.append(content)
            
            # Combine all content and rephrase using chat model
            combined_content = "\n\n".join(all_content)
            rephrased_content = self.rephrase_with_chat_model(combined_content, query)
            
            response += rephrased_content
            
            # Add source information
            response += "\n\n**Sources:**\n"
            for i, result in enumerate(results, 1):
                if result.get('title'):
                    response += f"- {result['title']}\n"
                elif result.get('url'):
                    response += f"- {result['url']}\n"
                else:
                    response += f"- Employee Handbook Section {i}\n"
           
            return response
           
        except Exception as e:
            return f"Error querying the Contoso Handbook: {str(e)}"
    
    def extract_relevant_sentences(self, content: str, keywords: List[str]) -> str:
        """Extract sentences that contain relevant keywords"""
        sentences = content.split('.')
        relevant_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if any(keyword.lower() in sentence.lower() for keyword in keywords):
                relevant_sentences.append(sentence)
        
        if relevant_sentences:
            return '. '.join(relevant_sentences[:3]) + '.'  # Limit to 3 most relevant sentences
        
        return content  # Return original content if no specific matches found
if __name__ == "__main__":
    search_plugin = ContosoSearchPlugin()
    query = "What is Contoso's vacation policy?"
    result = search_plugin.query_handbook(query)
    print(result)