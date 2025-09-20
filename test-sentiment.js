// Quick test of the new function
const { fetchAllArticlesWithSentiment } = require('./src/lib/articles.ts');

async function test() {
  try {
    console.log('Testing fetchAllArticlesWithSentiment...');
    const result = await fetchAllArticlesWithSentiment(2);
    console.log('Sources:', Object.keys(result));
    console.log('GMA articles with sentiment:', result.GMA?.length || 0);
    if (result.GMA && result.GMA.length > 0) {
      console.log('First GMA article sentiment:', result.GMA[0].sentiment);
    }
  } catch (error) {
    console.error('Error:', error.message);
  }
}

test();
