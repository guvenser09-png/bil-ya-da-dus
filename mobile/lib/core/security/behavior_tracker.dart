class BehaviorTracker {
  static final List<double> _answerTimes = [];

  static void recordAnswerTime(double seconds) {
    _answerTimes.add(seconds);
    if (_answerTimes.length > 20) {
      _answerTimes.removeAt(0);
    }
  }

  static bool isSuspiciouslyFast() =>
      _answerTimes.length >= 5 && _answerTimes.every((t) => t < 0.5);

  static void reset() => _answerTimes.clear();

  static Map<String, dynamic> getSummary() => {
        'answer_times': List.from(_answerTimes),
        'suspicious': isSuspiciouslyFast(),
        'count': _answerTimes.length,
      };
}
