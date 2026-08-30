import unittest

from rag.generator import GeminiFileSearchAnswerGenerator, NO_EVIDENCE_SENTINEL


class Object:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeRetriever:
    def __init__(self, interaction):
        self.interaction = interaction
        self.calls = []

    def generate(self, question, *, system_instruction, **options):
        self.calls.append((question, system_instruction))
        return self.interaction


class GeminiFileSearchAnswerGeneratorTests(unittest.TestCase):
    def test_generator_keeps_text_answer_and_file_citation_provenance(self):
        claim = "Python and Flask are listed skills."
        output = claim
        start = 0
        end = len(claim.encode("utf-8"))
        interaction = Object(
            steps=[
                Object(
                    type="model_output",
                    content=[
                        Object(
                            type="text",
                            text=output,
                            annotations=[
                                Object(
                                    type="file_citation",
                                    custom_metadata={
                                        "source_id": "skills-and-tools",
                                        "content_sha256": "known-hash",
                                    },
                                    document_uri="fileSearchStores/test/documents/skills",
                                    file_name="skills.md",
                                    start_index=start,
                                    end_index=end,
                                )
                            ],
                        )
                    ],
                )
            ]
        )
        retriever = FakeRetriever(interaction)

        result = GeminiFileSearchAnswerGenerator(retriever).answer("Which frameworks are listed?")

        self.assertTrue(result.answerable)
        self.assertEqual(result.claims[0].text, claim)
        self.assertEqual(result.claims[0].start_index, start)
        self.assertEqual(result.file_citations[0].source_id, "skills-and-tools")
        self.assertEqual(result.file_citations[0].document_name, "fileSearchStores/test/documents/skills")
        self.assertEqual(result.file_citations[0].file_name, "skills.md")
        self.assertIn("File Search", retriever.calls[0][1])

    def test_generator_accepts_list_shaped_custom_metadata(self):
        claim = "Python is listed as a skill."
        output = claim
        start = 0
        interaction = Object(
            steps=[
                Object(
                    type="model_output",
                    content=[
                        Object(
                            type="text",
                            text=output,
                            annotations=[
                                Object(
                                    type="file_citation",
                                    custom_metadata=[
                                        Object(key="source_id", string_value="skills-and-tools"),
                                        Object(key="content_sha256", string_value="known-hash"),
                                    ],
                                    document_uri="fileSearchStores/test/documents/skills",
                                    start_index=start,
                                    end_index=start + len(claim.encode("utf-8")),
                                )
                            ],
                        )
                    ],
                )
            ]
        )

        result = GeminiFileSearchAnswerGenerator(FakeRetriever(interaction)).answer("What skill is listed?")

        self.assertTrue(result.answerable)
        self.assertEqual(result.file_citations[0].content_sha256, "known-hash")

    def test_generator_compares_claims_and_citations_using_utf8_byte_offsets(self):
        claim = "Mihir's r\u00e9sum\u00e9 lists Docker as a skill."
        output = claim
        byte_start = 0
        byte_end = byte_start + len(claim.encode("utf-8"))
        interaction = Object(
            steps=[
                Object(
                    type="model_output",
                    content=[
                        Object(
                            type="text",
                            text=output,
                            annotations=[
                                Object(
                                    type="file_citation",
                                    custom_metadata={
                                        "source_id": "skills-and-tools",
                                        "content_sha256": "known-hash",
                                    },
                                    document_uri="fileSearchStores/test/documents/skills",
                                    start_index=byte_start,
                                    end_index=byte_end,
                                )
                            ],
                        )
                    ],
                )
            ]
        )

        result = GeminiFileSearchAnswerGenerator(FakeRetriever(interaction)).answer(
            "Which skill is listed?"
        )

        self.assertEqual(result.claims[0].start_index, byte_start)
        self.assertEqual(result.file_citations[0].end_index, byte_end)

    def test_chunk_text_in_source_is_not_treated_as_document_identity(self):
        claim = "Python is listed as a skill."
        output = claim
        start = 0
        interaction = Object(
            steps=[
                Object(
                    type="model_output",
                    content=[
                        Object(
                            type="text",
                            text=output,
                            annotations=[
                                Object(
                                    type="file_citation",
                                    custom_metadata={
                                        "source_id": "skills-and-tools",
                                        "content_sha256": "known-hash",
                                    },
                                    source="Python is listed as a skill.",
                                    start_index=start,
                                    end_index=start + len(claim),
                                )
                            ],
                        )
                    ],
                )
            ]
        )

        result = GeminiFileSearchAnswerGenerator(FakeRetriever(interaction)).answer(
            "What skill is listed?"
        )

        self.assertIsNone(result.file_citations[0].document_name)
        self.assertIsNone(result.file_citations[0].file_name)

    def test_no_evidence_sentinel_fails_closed(self):
        retriever = FakeRetriever(
            Object(
                steps=[
                    Object(
                        type="model_output",
                        content=[Object(type="text", text=NO_EVIDENCE_SENTINEL, annotations=[])],
                    )
                ]
            )
        )

        result = GeminiFileSearchAnswerGenerator(retriever).answer("Which framework is listed?")

        self.assertFalse(result.answerable)
        self.assertEqual(result.claims, ())

    def test_tool_question_uses_approved_source_navigation_only_for_retrieval(self):
        retriever = FakeRetriever(
            Object(
                steps=[
                    Object(
                        type="model_output",
                        content=[Object(type="text", text=NO_EVIDENCE_SENTINEL, annotations=[])],
                    )
                ]
            )
        )

        GeminiFileSearchAnswerGenerator(
            retriever,
            retrieval_hints=lambda _question: (
                "Potentially relevant approved source: Fleet Smart Vehicle Digital Twin Prototype "
                "(matching question terms: docker).",
            ),
        ).answer("Which project uses Docker?")

        retrieval_question, _ = retriever.calls[0]
        self.assertIn("Which project uses Docker?", retrieval_question)
        self.assertIn("Approved retrieval guide", retrieval_question)
        self.assertIn("Fleet Smart Vehicle Digital Twin Prototype", retrieval_question)
        self.assertNotIn("Docker Compose", retrieval_question)

    def test_complete_catalogue_request_does_not_apply_narrow_source_hints(self):
        retriever = FakeRetriever(
            Object(
                steps=[
                    Object(
                        type="model_output",
                        content=[Object(type="text", text=NO_EVIDENCE_SENTINEL, annotations=[])],
                    )
                ]
            )
        )

        GeminiFileSearchAnswerGenerator(
            retriever,
            retrieval_hints=lambda _question: ("Potentially relevant approved source: profile.",),
        ).answer("Tell me about all of Mihir's projects.", retrieval_scope="all_projects")

        retrieval_question, _ = retriever.calls[0]
        self.assertEqual(retrieval_question, "Tell me about all of Mihir's projects.")


if __name__ == "__main__":
    unittest.main()
