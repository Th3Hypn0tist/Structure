'use strict';

(function installScopeStyleRenderer(){
  if(typeof Renderer==='undefined'||!Renderer.prototype?.build)return;
  const originalBuild=Renderer.prototype.build;

  function semanticChannelColor(channel){
    const id=String(channel||'semantic');
    if(id==='gap')return'#FF176B';
    if(id==='impact'||id==='flow'||id==='dependencies')return'#FFD83D';
    if(id==='authority')return'#FF3B30';
    if(id==='relations'||id==='semantic'||id==='payload')return'#087CFF';
    return'#AAB2C2';
  }

  Renderer.prototype.build=function(scene){
    originalBuild.call(this,scene);

    // Scene node order and rendered box order are stable. Replace the old
    // hierarchy-parity presentation with the Scope Style color already carried
    // by each resolved scene node.
    let boxIndex=0;
    for(const obj of scene?.objects||[]){
      for(const node of obj.nodes||[]){
        if(boxIndex>=this.boxes.length)break;
        const explicit=node?.properties?.scope_color||node?.style?.color;
        if(explicit)this.boxes[boxIndex].color=hexColor(explicit,1);
        boxIndex++;
      }
    }

    // Preserve channel toggles but use stable semantic presentation colors so
    // causal paths, structural relations and gaps do not collapse visually.
    let lineIndex=0;
    for(const connection of scene?.connections||[]){
      if(lineIndex>=this.lines.length)break;
      const channel=String(connection.channel||'semantic');
      const state=S.channelState[channel]||{enabled:true};
      if(!state.enabled)continue;
      const alpha=connection.scope==='projection'?.72:.9;
      this.lines[lineIndex].color=hexColor(semanticChannelColor(channel),alpha);
      lineIndex++;
    }

    this.upload();
  };
})();
