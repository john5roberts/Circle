# Circle

Circle is a browser-based music harmony and progression tool designed for harmonic exploration, guitar practice, and song analysis.

Circle provides interactive chord progressions, Roman-numeral analysis, accompaniment patterns, chord-tone displays, and a searchable song library.

## Files

- `index.html` — the Circle application
- `Circle_song_library.json` — harmonic song data used by the Song browser

The application is designed to run through GitHub Pages.

## Song Library

Circle's song library is derived from harmonic annotations created for the McGill Billboard Project and subsequently incorporated into and corrected within the Coordinated Corpus of Popular Musics (CoCoPops).

Circle transforms these annotations into its own compact data format for harmonic visualization, playback, and analysis. The original annotation data is preserved separately from Circle's display and playback interpretations where practical.

The researchers and institutions responsible for the McGill Billboard Project and CoCoPops are not affiliated with Circle and are not responsible for Circle's software, interpretations, or presentation of the data.

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

Users wishing to reuse or redistribute the underlying source data should consult the licensing and usage information provided by the original projects.

## Copyright

Circle does not include song lyrics or commercial audio recordings.

Song titles, artist names, chord symbols, harmonic analyses, and related metadata are provided for musical study and navigation. Copyright in the underlying musical compositions and recordings remains with their respective rights holders.

Any links to third-party music services identify external recordings only. Those services operate under their own terms and licensing arrangements.

## Development

Circle is currently under active development.

Updates may include:

- expanded song-library support
- richer extended-chord notation
- section markers such as verse, chorus, and bridge
- key and meter changes within songs
- transposition
- links to reference recordings
- user-created and saved progressions
