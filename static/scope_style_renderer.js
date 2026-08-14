'use strict';

(function installScopeStyleRenderer(){
  if(typeof Renderer==='undefined'||!Renderer.prototype?.build)return;
  const originalBuild=Renderer.prototype.build;

  Renderer.prototype.build=function(scene){
    originalBuild.call(this,scene);

    // The base renderer predates Scope Style and colors nodes by hierarchy
    // parity. Scene node order and rendered box order are stable, so replace
    // those presentation colors with the already-resolved Scope Style colors
    // after geometry construction. No semantic membership is changed here.
    let boxIndex=0;
    for(const obj of scene?.objects||[]){
      for(const node of obj.nodes||[]){
        if(boxIndex>=this.boxes.length)break;
        const explicit=node?.properties?.scope_color||node?.style?.color;
        if(explicit)this.boxes[boxIndex].color=hexColor(explicit,1);
        boxIndex++;
      }
    }

    // Re-upload instance buffers after presentation colors are replaced.
    this.upload();
  };
})();
