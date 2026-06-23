# Rewrite Techniques Reference

## Tier 1 (Priority)

### 1. Sentence Restructuring
Change sentence structure while preserving meaning.

**Before:** The model was trained on a large dataset to achieve high accuracy.
**After:** To achieve high accuracy, we trained the model on a large dataset.

**Before:** It has been shown that deep learning improves performance.
**After:** Deep learning demonstrably improves performance.

**Effectiveness:** ★★★★★ (Most effective for reducing AIGC detection)

### 2. Active/Passive Conversion
Switch between active and passive voice.

**Before:** The experiment was conducted by the researchers.
**After:** The researchers conducted the experiment.

**Before:** We observed significant improvements.
**After:** Significant improvements were observed.

**Effectiveness:** ★★★★★

### 3. Split Long Sentences
Break complex sentences into shorter ones.

**Before:** Although the model was trained on a large dataset, it failed to generalize to unseen data, which suggests that the training procedure needs to be revised.
**After:** The model was trained on a large dataset. However, it failed to generalize to unseen data. This suggests that the training procedure needs revision.

**Effectiveness:** ★★★★☆

### 4. Merge Short Sentences
Combine short sentences into longer, more natural ones.

**Before:** The model performed well. The accuracy was high. The results were consistent.
**After:** The model performed well, achieving high accuracy with consistent results.

**Effectiveness:** ★★★★☆

### 5. Citation Position Moving
Change where citations appear in sentences.

**Before:** Deep learning has been shown to be effective (Smith et al., 2023).
**After:** As demonstrated by Smith et al. (2023), deep learning proves effective.

**Before:** Previous studies [1, 2] have addressed this problem.
**After:** This problem has been addressed in earlier work [1, 2].

**Effectiveness:** ★★★☆☆

## Tier 2 (Common)

### 6. Synonym Replacement
Replace words with synonyms.

**Before:** The results show significant improvement.
**After:** The findings demonstrate notable enhancement.

**Before:** We used a large dataset.
**After:** We employed a substantial corpus.

**Effectiveness:** ★★★★☆

### 7. Add Modifiers
Insert qualifying words to break AI patterns.

**Before:** The method achieves good results.
**After:** The method consistently achieves good results across multiple benchmarks.

**Before:** Performance improved.
**After:** Performance improved noticeably under controlled conditions.

**Effectiveness:** ★★★☆☆

### 8. Remove Redundancy
Eliminate unnecessary words and phrases.

**Before:** It is important to note that the results are significant.
**After:** The results are significant.

**Before:** In order to achieve this goal, we implemented the following approach.
**After:** To achieve this, we implemented:

**Effectiveness:** ★★★☆☆

### 9. Adjust Word Order
Change word order within sentences.

**Before:** We conducted experiments to validate our approach.
**After:** To validate our approach, we conducted experiments.

**Before:** The model achieved state-of-the-art performance on the benchmark.
**After:** On the benchmark, the model achieved state-of-the-art performance.

**Effectiveness:** ★★★☆☆

### 10. Add Transitions
Insert transitional phrases for natural flow.

**Before:** The model was trained. The results were analyzed.
**After:** The model was trained. Subsequently, the results were analyzed.

**Before:** We tested the hypothesis. The data supported it.
**After:** We tested the hypothesis. Importantly, the data supported it.

**Effectiveness:** ★★☆☆☆

## Tier 3 (Auxiliary)

### 11. Concretization
Replace abstract claims with specific examples.

**Before:** The method performs well on various tasks.
**After:** The method performs well on classification, detection, and segmentation tasks.

**Before:** Many applications benefit from this approach.
**After:** Applications in medical imaging, autonomous driving, and robotics benefit from this approach.

**Effectiveness:** ★★★☆☆

### 12. Abstraction
Replace specific claims with more general ones.

**Before:** The model achieved 95.3% accuracy on CIFAR-10.
**After:** The model achieved over 95% accuracy on the benchmark.

**Before:** We used ResNet-50 as the backbone.
**After:** We used a standard convolutional architecture as the backbone.

**Effectiveness:** ★★☆☆☆

### 13. Causal Inversion
Reverse cause-effect order.

**Before:** The model improved because we added more data.
**After:** Adding more data led to model improvement.

**Before:** Performance decreased due to overfitting.
**After:** Overfitting caused a decrease in performance.

**Effectiveness:** ★★★☆☆

### 14. Condition Restructuring
Change conditional expressions.

**Before:** If the learning rate is too high, the model diverges.
**After:** The model diverges when the learning rate exceeds a threshold.

**Before:** When the dataset is small, regularization is essential.
**After:** Small datasets require regularization to prevent overfitting.

**Effectiveness:** ★★★☆☆

### 15. Negation Reversal
Express the same idea using negation.

**Before:** The model performs well.
**After:** The model does not underperform.

**Before:** The results are significant.
**After:** The results are not negligible.

**Note:** Use sparingly — overuse creates awkward prose.

**Effectiveness:** ★★☆☆☆
