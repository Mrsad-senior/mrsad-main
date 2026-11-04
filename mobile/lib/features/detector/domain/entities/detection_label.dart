/// The detector's verdict. Its own thresholds are 0.5 (suspicious) and 0.8
/// (injection); the gateway applies each tool's thresholds on top.
enum DetectionLabel { benign, suspicious, injection }
