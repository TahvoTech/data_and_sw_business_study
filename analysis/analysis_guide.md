# Data Analysis for Software Business Model Study

This notebook analyzes the evidence collected by the auto-research pipeline to identify new business models in SMB software development companies.

## Dataset Overview

First, let's load the merged evidence dataset and explore its structure:

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import re
from wordcloud import WordCloud
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Load the master evidence dataset
df = pd.read_csv('../out/master_evidence.csv')

print(f"Dataset shape: {df.shape}")
print(f"Companies: {df['Company'].nunique()}")
print(f"Total evidence quotes: {len(df[df['EvidenceQuote'].str.strip() != ''])}")
print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
```

## Evidence Quality Assessment

```python
# Analyze evidence quality
df['has_evidence'] = df['EvidenceQuote'].str.strip() != ''
df['evidence_length'] = df['EvidenceQuote'].str.len()

# Company-level analysis
company_stats = df.groupby('Company').agg({
    'has_evidence': 'sum',
    'evidence_length': 'sum',
    'SearchKeyword': 'count'
}).rename(columns={'SearchKeyword': 'total_searches'})

print("Top companies by evidence collected:")
print(company_stats.sort_values('has_evidence', ascending=False).head(10))
```

## Business Model Pattern Analysis

```python
# Define business model keywords for pattern matching
business_model_patterns = {
    'SaaS': ['saas', 'software as a service', 'subscription', 'cloud-based', 'monthly fee'],
    'Platform': ['platform', 'marketplace', 'ecosystem', 'third-party', 'integration'],
    'Freemium': ['freemium', 'free tier', 'free version', 'premium features'],
    'Open Source': ['open source', 'open-source', 'github', 'community', 'contributions'],
    'Consulting': ['consulting', 'custom development', 'implementation', 'professional services'],
    'API-first': ['api', 'developer platform', 'integration', 'webhook'],
    'Data Analytics': ['analytics', 'insights', 'dashboard', 'reporting', 'metrics'],
    'AI/ML': ['artificial intelligence', 'machine learning', 'ai', 'ml', 'automation']
}

def detect_business_models(text):
    """Detect business model patterns in text"""
    if pd.isna(text) or text.strip() == '':
        return []
    
    text_lower = text.lower()
    detected = []
    
    for model, keywords in business_model_patterns.items():
        if any(keyword in text_lower for keyword in keywords):
            detected.append(model)
    
    return detected

# Apply pattern detection
df['detected_models'] = df['EvidenceQuote'].apply(detect_business_models)
df['model_count'] = df['detected_models'].apply(len)
```

## Company Categorization

```python
# Categorize companies by detected business models
company_models = df[df['has_evidence']].groupby('Company')['detected_models'].apply(
    lambda x: list(set([model for sublist in x for model in sublist]))
).reset_index()

company_models['primary_model'] = company_models['detected_models'].apply(
    lambda x: x[0] if x else 'Traditional'
)

print("Business model distribution:")
print(company_models['primary_model'].value_counts())
```

## Visualization

```python
# Create visualizations
plt.figure(figsize=(15, 10))

# 1. Evidence collection by company
plt.subplot(2, 3, 1)
top_companies = company_stats.sort_values('has_evidence', ascending=False).head(10)
plt.barh(range(len(top_companies)), top_companies['has_evidence'])
plt.yticks(range(len(top_companies)), top_companies.index)
plt.title('Evidence Collected by Company')
plt.xlabel('Number of Evidence Quotes')

# 2. Business model distribution
plt.subplot(2, 3, 2)
model_counts = company_models['primary_model'].value_counts()
plt.pie(model_counts.values, labels=model_counts.index, autopct='%1.1f%%')
plt.title('Primary Business Model Distribution')

# 3. Evidence quality distribution
plt.subplot(2, 3, 3)
plt.hist(df[df['has_evidence']]['evidence_length'], bins=30, alpha=0.7)
plt.title('Evidence Quote Length Distribution')
plt.xlabel('Characters')
plt.ylabel('Frequency')

# 4. Search keyword effectiveness
plt.subplot(2, 3, 4)
keyword_success = df.groupby('SearchKeyword')['has_evidence'].mean().sort_values(ascending=False).head(10)
plt.barh(range(len(keyword_success)), keyword_success.values)
plt.yticks(range(len(keyword_success)), keyword_success.index)
plt.title('Search Keyword Effectiveness')
plt.xlabel('Success Rate')

# 5. Timeline analysis
plt.subplot(2, 3, 5)
df['Date'] = pd.to_datetime(df['Date'])
daily_evidence = df[df['has_evidence']].groupby(df['Date'].dt.date).size()
plt.plot(daily_evidence.index, daily_evidence.values)
plt.title('Evidence Collection Timeline')
plt.xticks(rotation=45)

# 6. Multi-model companies
plt.subplot(2, 3, 6)
model_diversity = company_models['detected_models'].apply(len)
plt.hist(model_diversity, bins=range(0, model_diversity.max()+2), alpha=0.7)
plt.title('Business Model Diversity per Company')
plt.xlabel('Number of Different Models Detected')
plt.ylabel('Number of Companies')

plt.tight_layout()
plt.show()
```

## Word Cloud Analysis

```python
# Create word cloud from evidence quotes
all_evidence = ' '.join(df[df['has_evidence']]['EvidenceQuote'].values)

# Clean text for word cloud
stop_words = set(stopwords.words('english'))
stop_words.update(['software', 'company', 'development', 'business', 'service', 'solution'])

wordcloud = WordCloud(width=800, height=400, 
                     background_color='white',
                     stopwords=stop_words,
                     max_words=100).generate(all_evidence)

plt.figure(figsize=(10, 5))
plt.imshow(wordcloud, interpolation='bilinear')
plt.axis('off')
plt.title('Most Common Terms in Evidence Quotes')
plt.show()
```

## Detailed Company Analysis

```python
# Detailed analysis for specific companies
def analyze_company(company_name):
    """Detailed analysis for a specific company"""
    company_data = df[df['Company'] == company_name]
    
    print(f"=== Analysis for {company_name} ===")
    print(f"Total searches: {len(company_data)}")
    print(f"Evidence found: {company_data['has_evidence'].sum()}")
    print(f"Success rate: {company_data['has_evidence'].mean():.2%}")
    
    # Show evidence quotes
    evidence = company_data[company_data['has_evidence']]
    if len(evidence) > 0:
        print("\nEvidence quotes:")
        for idx, row in evidence.iterrows():
            print(f"- [{row['SearchKeyword']}] {row['EvidenceQuote'][:200]}...")
    
    # Detected business models
    models = [model for sublist in company_data['detected_models'] for model in sublist]
    if models:
        print(f"\nDetected business models: {list(set(models))}")
    
    return company_data

# Example: analyze top companies
top_companies = company_stats.sort_values('has_evidence', ascending=False).head(3).index
for company in top_companies:
    analyze_company(company)
    print("-" * 50)
```

## Export Results

```python
# Create summary reports
summary_report = {
    'total_companies': df['Company'].nunique(),
    'total_evidence_quotes': len(df[df['has_evidence']]),
    'avg_evidence_per_company': company_stats['has_evidence'].mean(),
    'most_effective_keywords': keyword_success.head(5).to_dict(),
    'business_model_distribution': model_counts.to_dict()
}

# Save detailed company analysis
company_analysis = company_models.merge(company_stats, left_on='Company', right_index=True)
company_analysis.to_csv('../out/company_business_model_analysis.csv', index=False)

# Save keyword effectiveness
keyword_analysis = df.groupby('SearchKeyword').agg({
    'has_evidence': ['count', 'sum', 'mean'],
    'evidence_length': 'sum'
}).round(3)
keyword_analysis.to_csv('../out/keyword_effectiveness.csv')

print("Analysis complete! Check out/ directory for detailed results.")
```
