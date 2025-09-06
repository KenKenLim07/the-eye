import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';

export async function GET() {
  try {
    console.log('🔍 Testing Supabase connection from API route...');
    
    const result = await supabaseServer
      .from('articles')
      .select('*')
      .eq('source', 'ABS-CBN')
      .limit(3);
    
    if (result.error) {
      console.error('❌ Supabase Error:', result.error);
      return NextResponse.json({ 
        success: false, 
        error: result.error.message 
      });
    }
    
    console.log('✅ Supabase Success! Articles found:', result.data.length);
    
    return NextResponse.json({ 
      success: true, 
      articles: result.data,
      count: result.data.length 
    });
    
  } catch (error) {
    console.error('❌ API Error:', error);
    return NextResponse.json({ 
      success: false, 
      error: error instanceof Error ? error.message : 'Unknown error' 
    });
  }
}
