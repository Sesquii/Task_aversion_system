# Emotion Filter for Recommendations System - Assessment

## Executive Summary

**Recommendation: Implement emotion filter with separate initialization emotion tracking**

Adding an emotion filter to the recommendations system would provide value, but requires careful design to align with the continuous emotion tracking philosophy. The system should track emotions at initialization separately from current persistent emotions.

## Current System Design

### Emotion Tracking Philosophy
- **Continuous Tracking**: Emotions should reflect your current emotional state as you use the app
- **Persistent State**: Emotions persist across pages and tasks, updating as you initialize/complete tasks
- **Task-Specific Capture**: When initializing/completing a task, emotions are captured at that moment

### Current Implementation
- Emotions are stored in `predicted.emotion_values` (dict) for initialization
- Emotions are stored in `actual.emotion_values` (dict) for completion
- Persistent emotions are stored in `user_state.persistent_emotion_values`
- Recommendations system currently filters by: duration, relief, cognitive load, emotional load

## Proposed Emotion Filter Design

### For Task Templates (Uninitialized Tasks)
- **Filter by**: Average emotion value across all historical initializations of that task
- **Calculation**: Average `predicted.emotion_values[emotion_name]` for all instances of that task
- **Use Case**: "Show me tasks that typically make me feel anxious" or "Show me tasks that usually give me excitement"

### For Initialized Tasks
- **Filter by**: Emotion value from the specific initialization
- **Calculation**: Use `predicted.emotion_values[emotion_name]` from that instance
- **Use Case**: "Show me initialized tasks where I felt anxious" or "Rank by excitement level at initialization"

## Value Assessment

### ✅ **High Value Scenarios**

1. **Emotional State Matching**
   - Filter tasks by current emotional state: "I'm feeling anxious, show me tasks that typically help reduce anxiety"
   - Match tasks to emotional needs: "I need motivation, show me tasks that usually give me excitement"

2. **Pattern Recognition**
   - Identify which tasks correlate with positive emotions
   - Find tasks that help transition from negative to positive emotional states

3. **Personalized Recommendations**
   - "Tasks that make me feel accomplished" (high relief + positive emotions)
   - "Tasks I can do when I'm feeling low energy" (low cognitive load + calming emotions)

### ⚠️ **Design Considerations**

1. **Separation of Concerns**
   - **Initialization Emotions**: Captured at task start, stored in `predicted.emotion_values`
   - **Current Persistent Emotions**: Continuously updated, stored in `user_state.persistent_emotion_values`
   - **Recommendations should use**: Initialization emotions (historical averages) for templates, initialization emotions for initialized tasks

2. **Data Availability**
   - Requires sufficient historical data to calculate meaningful averages
   - New tasks/templates may not have emotion data yet
   - Need fallback behavior when emotion data is missing

3. **UI Complexity**
   - Need emotion selector in recommendations filter UI
   - Should support multiple emotions (AND/OR logic?)
   - Range selection (e.g., "anxiety > 50") vs exact match

## Implementation Recommendations

### Phase 1: Backend Support
1. Add emotion averaging to `Analytics.recommendations()`
2. Calculate average emotion values per task template from historical initializations
3. Add emotion filter parameter to recommendations API

### Phase 2: Filter Logic
1. For templates: Filter by average emotion value (with threshold, e.g., > 50)
2. For initialized tasks: Filter by initialization emotion value
3. Support ranking by emotion value (ascending/descending)

### Phase 3: UI Integration
1. Add emotion dropdown/selector to recommendations filter UI
2. Add emotion value range slider (optional)
3. Show emotion values in recommendation cards

## Alternative: Emotion-Based Ranking

Instead of filtering, could add emotion-based ranking:
- "Rank by excitement level" (high excitement first)
- "Rank by anxiety level" (low anxiety first)
- This provides similar value with less complexity

## Conclusion

**Value: Medium-High** - Emotion filtering would add meaningful personalization, but requires careful design to maintain the continuous emotion tracking philosophy. The key is using initialization emotions (historical averages) rather than current persistent emotions for recommendations.

**Priority: Medium** - Useful feature, but not critical. Consider implementing after fixing emotion persistence issues and ensuring the emotion tracking system is working as intended.
