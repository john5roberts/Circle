# Circle

Circle is a browser-based music harmony and progression tool designed for harmonic exploration, guitar practice, soloing practice, and song analysis.

Circle provides interactive chord progressions, Roman-numeral analysis, accompaniment patterns, chord-tone displays, and a searchable song library. The current main release is **Circle v1.120**.

## Files

- `index.html` — the Circle application
- `Circle_song_library.json` — harmonic song data used by the Song browser

The application is designed to run through GitHub Pages.

## Song Library

The current Circle song library contains **764 songs**.

- **739 songs** are derived from harmonic annotations created for the McGill Billboard Project and subsequently incorporated into and corrected within the Coordinated Corpus of Popular Musics (CoCoPops).
- **25 additional jazz standards** are derived from the **ChoCo (Chord Corpus) v1.0.0 Real Book partition**. These entries were added after compatibility testing of ChoCo's symbolic chord and measure/beat data with Circle.

Circle transforms source annotations into its own compact data format for harmonic visualization, playback, and analysis. Detailed source chord symbols and provenance are preserved where practical.

The 25 currently included Real Book entries are the validated compatibility set used during development. They retain their ChoCo source-file provenance so they can later be reconciled with a larger Real Book import.

The researchers and institutions responsible for the McGill Billboard Project, CoCoPops, and ChoCo are not affiliated with Circle and are not responsible for Circle's software, interpretations, or presentation of the data.

## Song Playback and Accompaniment

Each song can carry preferred accompaniment defaults for:

- guitar rhythm
- bass pattern
- drum pattern

Circle applies these defaults when a song is loaded. They are starting choices only; the user can change the accompaniment controls manually at any time.

Accompaniment assignments are intended to provide stylistic variety and a useful practice context. They should not be interpreted as transcriptions of the accompaniment used on the original recording.

## Harmonic Color Coding

Circle uses color to distinguish notes that belong to the active tonal collection from notes that do not.

For chord-level coloring in the progression buttons and Circle-of-fifths display, the chord is evaluated by its **triad (root, third, and fifth)** rather than by every extension in the full chord.

This allows, for example, a **C7 chord in C major** to remain green at the chord level because its C-E-G triad is diatonic, while the **B♭ (♭7)** is still shown in red in the interval display beneath the chord.

Extensions and alterations therefore retain their individual interval colors without causing the entire chord or Circle wedge to be marked out of key.

## Acknowledgments

### McGill Billboard Project

The McGill Billboard Project provides expert harmonic annotations of popular music recordings. The original McGill Billboard annotations were released under CC0.

Users of the dataset are asked to acknowledge the following work:

J. Ashley Burgoyne, Jonathan Wild, and Ichiro Fujinaga,  
"An Expert Ground Truth Set for Audio Chord Recognition and Music Analysis,"  
Proceedings of the 12th International Society for Music Information Retrieval Conference (ISMIR), 2011, pp. 633–638.

McGill Billboard Project:  
https://ddmal.ca/research/The_McGill_Billboard_Project_(Chord_Analysis_Dataset)/

### CoCoPops

Circle also makes use of the corrected and expanded Billboard harmonic data distributed as part of the Coordinated Corpus of Popular Musics (CoCoPops).

Relevant citation:

Claire Arthur and Nathaniel Condit-Schultz,  
"The Coordinated Corpus of Popular Musics (CoCoPops): A Meta-Corpus of Melodic and Harmonic Transcriptions,"  
Proceedings of the International Society for Music Information Retrieval Conference (ISMIR), 2023.

CoCoPops repository:  
https://github.com/Computational-Cognitive-Musicology-Lab/CoCoPops

### ChoCo (Chord Corpus)

Circle also uses a small validated set of symbolic jazz-standard annotations from **ChoCo v1.0.0**, specifically its **Real Book** partition.

The ChoCo material is converted from its standardized chord representation and symbolic measure/beat timing into Circle's compact song format. Circle preserves source identifiers so imported songs can be traced back to their ChoCo JAMS files.

The Real Book partition used for the current Circle compatibility set is distributed in ChoCo under **CC BY 4.0**.

ChoCo repository:  
https://github.com/smashub/choco

Users wishing to reuse or redistribute the underlying source data should consult the licensing and usage information provided by the original projects.

## Copyright

Circle does not include song lyrics or commercial audio recordings.

Song titles, artist names, chord symbols, harmonic analyses, and related metadata are provided for musical study and navigation. Copyright in the underlying musical compositions and recordings remains with their respective rights holders.

Any links to third-party music services identify external recordings only. Those services operate under their own terms and licensing arrangements.

## Development

Circle is currently under active development.

Current and planned work includes:

- expansion beyond the current 25-song ChoCo Real Book compatibility set
- preservation and use of source tempo information where available
- improved support for meter changes and less-common meters such as 5/4 and 7/4
- richer extended-chord notation and harmonic interpretation
- section markers such as verse, chorus, and bridge
- key changes and local tonal-center changes within songs
- transposition
- links to reference recordings
- user-created and saved progressions
