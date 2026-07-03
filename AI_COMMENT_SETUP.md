# AI Comment Generation Setup

This feature adds AI-powered comment generation to your music platform using OpenRouter with `deepseek/deepseek-v4-pro` by default.

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variable
You need to set your OpenRouter API key as an environment variable:

**Windows:**
```cmd
set OPENROUTER_API_KEY=your_api_key_here
```

**Linux/Mac:**
```bash
export OPENROUTER_API_KEY=your_api_key_here
```

Optional settings:

```bash
export OPENROUTER_MODEL=deepseek/deepseek-v4-pro
export OPENROUTER_SITE_NAME=EasyCore
export OPENROUTER_SITE_URL=http://127.0.0.1:5015
```

### 3. Get OpenRouter API Key
1. Go to [OpenRouter](https://openrouter.ai/)
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

- Uses `deepseek/deepseek-v4-pro` by default
- Each comment generation uses approximately 150 tokens
- Actual cost depends on current OpenRouter pricing for the selected model
- Monitor your OpenRouter usage dashboard for actual costs

## Troubleshooting

### "OPENROUTER_API_KEY environment variable is required"
- Make sure you've set the environment variable correctly
- Restart your Flask application after setting the variable

### "Error generating comment"
- Check your OpenRouter API key is valid
- Ensure you have credits in your OpenRouter account
- Check your internet connection

### Comments not generating
- Verify the API key has the correct permissions
- Check the OpenRouter service status
- Review the browser console for JavaScript errors

## Security Notes

- API key is only used server-side
- No API key is exposed to the client
- Comments are generated on-demand, not stored
- You can edit/delete generated comments like any other comment
