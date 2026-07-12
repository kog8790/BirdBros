from competitor_app.vision import parse_analysis_response


def test_simple_mode_does_not_fabricate_evidence_fields():
    result = parse_analysis_response(
        '{"rewardable": true, "bestFrameIndex": 2, "reason": "yes", "justification": "visible"}',
        mode="simple",
    )

    assert result.rewardable is True
    assert result.best_frame_index == 2
    assert result.subject_present is None
    assert result.object_present is None
    assert result.action_observed is None
    assert result.target_zone_visible is None


def test_advanced_mode_parses_evidence_fields():
    result = parse_analysis_response(
        """
        ```json
        {
          "subjectPresent": true,
          "subjectLabel": "bird",
          "objectPresent": true,
          "objectLabel": "wrapper",
          "actionObserved": true,
          "targetZoneVisible": true,
          "rewardable": true,
          "bestFrameIndex": 3,
          "reason": "matched",
          "justification": "sequence shows deposit"
        }
        ```
        """,
        mode="advanced",
    )

    assert result.rewardable is True
    assert result.subject_present is True
    assert result.subject_label == "bird"
    assert result.object_label == "wrapper"
