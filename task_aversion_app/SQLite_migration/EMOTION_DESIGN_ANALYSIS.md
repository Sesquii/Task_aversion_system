# Emotion Table Design Analysis

## Current Design (CSV-based)

**Current Implementation:**
- Each user maintains their own list of emotions in `emotions.csv`
- Simple list of emotion strings: `['excited', 'bored', 'anxious', 'Dread', 'Tired']`
- Users manually add emotions as they encounter them
- Case-insensitive duplicate detection handled in application logic

**Current File Structure:**
```csv
emotion
excited
bored
anxious
Dread
Tired
```

## Proposed Design Options

### Option 1: Master Dictionary Table (Shared Emotion Library)

**Concept:**
- Single master table with all possible emotions from a comprehensive emotion dictionary/thesaurus
- Pre-populated with emotion words (e.g., from Plutchik's emotion wheel, NRC Emotion Lexicon, etc.)
- Users can search/filter from this master list
- Manual input cross-references against master list (fuzzy matching)

**Database Schema:**
```sql
emotions (
    emotion_id INTEGER PRIMARY KEY,
    emotion TEXT UNIQUE NOT NULL,
    category TEXT,              -- e.g., 'basic', 'joy', 'sadness', 'anger'
    intensity_level INTEGER,    -- 1-10 scale (optional)
    synonyms TEXT,              -- JSON array of synonyms
    created_at DATETIME
)

user_emotions (
    user_id TEXT,
    emotion_id INTEGER REFERENCES emotions(emotion_id),
    usage_count INTEGER DEFAULT 0,
    last_used DATETIME,
    PRIMARY KEY (user_id, emotion_id)
)
```

**Pros:**
- ✅ Standardized emotion vocabulary (better for analytics/ML)
- ✅ Easier to find emotions (search/filter)
- ✅ Cross-user analytics possible (same emotions across users)
- ✅ Prevents typos and variations (e.g., "anxious" vs "anxeity")
- ✅ Can include emotion metadata (categories, synonyms, intensity)
- ✅ Better for research/studies (standardized data)
- ✅ Cross-reference helps users discover emotions they forgot about

**Cons:**
- ❌ Requires research to populate comprehensive list (initial effort)
- ❌ Less flexible (users can't use highly personal/unique terms)
- ❌ May not include niche or domain-specific emotions
- ❌ More complex schema (master table + user preferences)
- ❌ Search/fuzzy matching logic needed for manual input

**Search/Cross-reference Logic:**
```python
def find_or_create_emotion(user_input: str):
    # 1. Exact match (case-insensitive)
    emotion = session.query(Emotion).filter(
        func.lower(Emotion.emotion) == user_input.lower()
    ).first()
    
    # 2. Fuzzy match (if no exact match)
    if not emotion:
        emotions = session.query(Emotion).all()
        matches = fuzzy_match(user_input, [e.emotion for e in emotions])
        if matches:
            # Show suggestions to user
            return suggest_emotions(matches)
    
    # 3. Add to user's used emotions
    user_emotion = UserEmotion(user_id=user_id, emotion_id=emotion.emotion_id)
    session.add(user_emotion)
```

**Data Sources for Master Dictionary:**
- Plutchik's Wheel of Emotions (8 basic + combinations)
- NRC Emotion Lexicon (~14,000 words with emotion associations)
- Basic Emotion List (joy, sadness, anger, fear, surprise, disgust, contempt)
- Extended emotion thesaurus (hundreds of emotion words)

### Option 2: User-Specific Dictionary (Current Approach, Database-backed)

**Concept:**
- Each user maintains their own emotion list (current behavior)
- Database just stores what each user has used
- No master dictionary or cross-referencing

**Database Schema:**
```sql
emotions (
    emotion_id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    emotion TEXT NOT NULL,
    usage_count INTEGER DEFAULT 0,
    last_used DATETIME,
    created_at DATETIME,
    UNIQUE(user_id, emotion)  -- Case-insensitive handled in app
)
```

**Pros:**
- ✅ Simple schema (one table)
- ✅ Fully flexible (users can use any term)
- ✅ Matches current user experience
- ✅ No research/curation needed
- ✅ Preserves user's personal vocabulary

**Cons:**
- ❌ No standardization (harder analytics)
- ❌ Users may misspell or use inconsistent terms
- ❌ Cross-user analytics difficult
- ❌ No discovery of new emotions (no suggestions)
- ❌ Can't leverage emotion research/metadata

### Option 3: Hybrid Approach

**Concept:**
- Master dictionary exists as reference
- Users can add custom emotions (not in master)
- Best of both worlds: standardization + flexibility

**Database Schema:**
```sql
emotions_master (
    emotion_id INTEGER PRIMARY KEY,
    emotion TEXT UNIQUE NOT NULL,
    category TEXT,
    is_standard BOOLEAN DEFAULT TRUE
)

user_emotions (
    user_id TEXT,
    emotion_id INTEGER REFERENCES emotions_master(emotion_id),
    is_custom BOOLEAN DEFAULT FALSE,  -- True if user created this
    usage_count INTEGER DEFAULT 0,
    last_used DATETIME,
    PRIMARY KEY (user_id, emotion_id)
)

-- Users can also add custom emotions not in master
emotions_custom (
    emotion_id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    emotion TEXT NOT NULL,
    created_at DATETIME
)
```

**Pros:**
- ✅ Standardization for common emotions
- ✅ Flexibility for personal/niche emotions
- ✅ Can migrate custom emotions to master over time
- ✅ Search works for both standard and custom
- ✅ Analytics can separate standard vs custom

**Cons:**
- ❌ Most complex schema
- ❌ Requires migration logic for existing data
- ❌ Need to decide when custom → standard

## Comparison Matrix

| Feature | Master Dict | User-Specific | Hybrid |
|---------|-------------|---------------|--------|
| **Standardization** | ✅ Excellent | ❌ None | ✅ Good |
| **Flexibility** | ❌ Limited | ✅ Excellent | ✅ Good |
| **Search/Discovery** | ✅ Excellent | ❌ None | ✅ Good |
| **Schema Complexity** | Medium | ✅ Simple | ❌ Complex |
| **Analytics** | ✅ Excellent | ❌ Difficult | ✅ Good |
| **Implementation Effort** | Medium | ✅ Low | ❌ High |
| **User Experience** | Good (with search) | ✅ Current (familiar) | Good |

## Recommendation

**For Migration 004: Start with Option 2 (User-Specific, Database-backed)**

**Rationale:**
1. **Matches current behavior** - Users are already comfortable with this
2. **Simple migration** - Easiest to implement now
3. **Can evolve later** - We can add master dictionary in future migration
4. **Low risk** - Preserves existing functionality exactly

**Future Enhancement Path:**
1. **Phase 1 (Now)**: Migrate to database with user-specific emotions
2. **Phase 2 (Later)**: Add optional master dictionary for suggestions
3. **Phase 3 (Future)**: Implement hybrid approach if needed

**For Option 1 (Master Dictionary) Implementation Later:**
- Research emotion lexicons (NRC, Plutchik, etc.)
- Create population script with ~500-2000 common emotions
- Add search/autocomplete UI
- Add fuzzy matching for manual input
- Migration script to match existing user emotions to master list

## Implementation Notes

### Current EmotionManager Methods:
- `list_emotions()` - Returns user's emotion list
- `add_emotion(emotion)` - Adds emotion (case-insensitive duplicate check)
- `remove_emotion(emotion)` - Removes emotion
- `search_emotions(query)` - Case-insensitive substring search

### Database Migration Considerations:
- Emotion uniqueness: Handle case-insensitive matching (SQLite doesn't support case-insensitive UNIQUE by default)
- Migration from CSV: Existing emotions should map cleanly
- Indexing: Index on `emotion` column for fast lookups
- User isolation: If multi-user support is planned, need `user_id` column

## Questions to Consider

1. **Multi-user support**: Do we need `user_id` column now, or later?
   - Current: Single user (default_user)
   - Future: Multi-user support

2. **Emotion normalization**: Should we normalize case in database?
   - Store as entered? ("anxious", "Anxious", "ANXIOUS")
   - Normalize to lowercase? (all stored as "anxious")

3. **Search behavior**: How should search work?
   - Exact match only?
   - Substring search?
   - Fuzzy matching?

4. **Analytics needs**: What analytics will use emotions?
   - If cross-user analytics planned → Master dictionary helpful
   - If single-user only → User-specific is fine

