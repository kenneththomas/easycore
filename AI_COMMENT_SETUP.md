# AI Comment Generation Setup

This feature adds AI-powered comment generation to your music platform using OpenAI's GPT-4o-mini model.

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variable
You need to set your OpenAI API key as an environment variable:

**Windows:**
```cmd
set OPENAI_API_KEY=your_api_key_here
```

**Linux/Mac:**
```bash
export OPENAI_API_KEY=your_api_key_here
```

### 3. Get OpenAI API Key
1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign up or log in
3. Go to API Keys section
4. Create a new API key
5. Copy the key and set it as the environment variable

## How It Works

### Track Comments
- On track detail pages, you'll see a "🤖 AI Comment" button next to the name field
- Click it to open a dropdown with comment style options
- Choose from predefined styles or enter a custom prompt
- The AI will generate a realistic comment based on the track and artist information
- The generated comment appears in the comment box where you can edit it before posting

### Artist Comments
- On artist detail pages, the same AI comment feature is available
- Comments are generated based on the artist's information, bio, and track count
- You can choose different comment styles or use custom prompts

## Comment Styles Available

1. **General fan comment** - Standard music fan reaction
2. **Enthusiastic comment** - Positive, excited response
3. **Thoughtful critique** - Balanced, analytical comment
4. **Just discovered** - First-time listener perspective
5. **Nostalgic comment** - Reminiscing about the music
6. **Technical analysis** - Focus on production/musical elements
7. **Emotional response** - Personal, emotional reaction
8. **Compare to other music** - Comparative analysis
9. **Custom prompt** - Your own specific instructions

## Features

- **Realistic Comments**: AI generates authentic-sounding music fan comments
- **Context Aware**: Uses track/artist information for relevant comments
- **Editable**: Generated comments can be modified before posting
- **Multiple Styles**: Various comment types for different scenarios
- **Custom Prompts**: Full control over comment generation
- **Error Handling**: Graceful handling of API errors

## Cost Considerations

- Uses GPT-4o-mini model (cost-effective)
- Each comment generation uses approximately 150 tokens
- Typical cost: ~$0.0001-0.0002 per comment
- Monitor your OpenAI usage dashboard for actual costs

## Troubleshooting

### "OPENAI_API_KEY environment variable is required"
- Make sure you've set the environment variable correctly
- Restart your Flask application after setting the variable

### "Error generating comment"
- Check your OpenAI API key is valid
- Ensure you have credits in your OpenAI account
- Check your internet connection

### Comments not generating
- Verify the API key has the correct permissions
- Check the OpenAI service status
- Review the browser console for JavaScript errors

## Security Notes

- API key is only used server-side
- No API key is exposed to the client
- Comments are generated on-demand, not stored
- You can edit/delete generated comments like any other comment
