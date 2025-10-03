"""
AI Comment Generator Module
Handles OpenAI API integration for generating fake engagement comments
"""

import os
import openai
from typing import Optional, Dict, Any
import logging
import maricon

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AICommentGenerator:
    def __init__(self):
        """Initialize the AI comment generator with OpenAI API key"""
        self.api_key = maricon.gptkey
        
        openai.api_key = self.api_key
        self.client = openai.OpenAI(api_key=self.api_key)
    
    def generate_track_comment(self, 
                             track_name: str, 
                             artist_name: str, 
                             custom_prompt: Optional[str] = None,
                             track_tags: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a fake comment for a track
        
        Args:
            track_name: Name of the track
            artist_name: Name of the artist
            custom_prompt: Custom prompt for comment generation
            track_tags: Tags associated with the track
            
        Returns:
            Dict containing the generated comment and metadata
        """
        try:
            # Default prompt if none provided
            if not custom_prompt:
                custom_prompt = f"What would a music fan think about {track_name} by {artist_name}?"
            
            # Build context for the AI
            context = f"""
            Generate a realistic music fan comment for the track "{track_name}" by {artist_name}.
            The comment should sound like it's from a real music listener who just discovered or enjoyed this track.
            Make it conversational, authentic, and engaging. Include specific details about the music.
            """
            
            if track_tags:
                context += f"\nTrack tags: {track_tags}"
            
            # Add custom prompt context
            context += f"\nSpecific focus: {custom_prompt}"
            
            # Generate the comment
            response = self.client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a music fan writing comments on a music platform. Write authentic, engaging comments that sound like real music listeners. Keep comments conversational and specific to the music."
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                max_completion_tokens=1000,

            )
            
            generated_comment = response.choices[0].message.content.strip()
            
            # Debug logging
            logger.info(f"GPT API Response: {response}")
            logger.info(f"Generated comment: {generated_comment}")
            logger.info(f"Response choices count: {len(response.choices)}")
            
            return {
                "success": True,
                "comment": generated_comment,
                "model": "gpt-5",
                "prompt_used": custom_prompt
            }
            
        except Exception as e:
            logger.error(f"Error generating track comment: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "comment": None
            }
    
    def generate_artist_comment(self, 
                               artist_name: str, 
                               custom_prompt: Optional[str] = None,
                               artist_bio: Optional[str] = None,
                               track_count: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate a fake comment for an artist
        
        Args:
            artist_name: Name of the artist
            custom_prompt: Custom prompt for comment generation
            artist_bio: Artist's biography
            track_count: Number of tracks by the artist
            
        Returns:
            Dict containing the generated comment and metadata
        """
        try:
            # Default prompt if none provided
            if not custom_prompt:
                custom_prompt = f"What would a music fan think about {artist_name} as an artist?"
            
            # Build context for the AI
            context = f"""
            Generate a realistic music fan comment about the artist "{artist_name}".
            The comment should sound like it's from a real music listener who appreciates this artist's work.
            Make it conversational, authentic, and engaging. Include specific details about the artist's music or style.
            """
            
            if artist_bio:
                context += f"\nArtist bio: {artist_bio[:200]}..."  # Truncate for context
            
            if track_count:
                context += f"\nArtist has {track_count} tracks available."
            
            # Add custom prompt context
            context += f"\nSpecific focus: {custom_prompt}"
            
            # Generate the comment
            response = self.client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a music fan writing comments on a music platform. Write authentic, engaging comments that sound like real music listeners. Keep comments conversational and specific to the artist's music and style."
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                max_completion_tokens=150,

            )
            
            generated_comment = response.choices[0].message.content.strip()
            
            # Debug logging
            logger.info(f"GPT API Response: {response}")
            logger.info(f"Generated comment: {generated_comment}")
            logger.info(f"Response choices count: {len(response.choices)}")
            
            return {
                "success": True,
                "comment": generated_comment,
                "model": "gpt-5",
                "prompt_used": custom_prompt
            }
            
        except Exception as e:
            logger.error(f"Error generating artist comment: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "comment": None
            }
    
    def get_default_prompts(self) -> Dict[str, str]:
        """
        Get a list of default prompts for different types of comments
        
        Returns:
            Dict of prompt categories and their default prompts
        """
        return {
            "general": "What would a music fan think about {artist_name} - {track_name}?",
            "positive": "Write an enthusiastic comment about {artist_name} - {track_name}",
            "critical": "Write a thoughtful, slightly critical comment about {artist_name} - {track_name}",
            "discovery": "Write a comment from someone who just discovered {artist_name} - {track_name}",
            "nostalgic": "Write a nostalgic comment about {artist_name} - {track_name}",
            "technical": "Write a comment focusing on the technical aspects of {artist_name} - {track_name}",
            "emotional": "Write an emotional comment about {artist_name} - {track_name}",
            "comparison": "Write a comment comparing {artist_name} - {track_name} to other music",
            "custom": "Custom prompt..."
        }

# Global instance
ai_generator = None

def get_ai_generator() -> AICommentGenerator:
    """Get or create the global AI comment generator instance"""
    global ai_generator
    if ai_generator is None:
        ai_generator = AICommentGenerator()
    return ai_generator
